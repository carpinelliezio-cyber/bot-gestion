import discord
from discord.ext import commands
import os
import re
from keep_alive import keep_alive
import asyncio
from datetime import timedelta, datetime
import collections

# ==========================================
# ⚙️ CONFIGURATION ULTRA-STRICTE
# ==========================================
MAX_MENTIONS = 4       # Mentions max autorisées par message
SPAM_LIMIT = 5         # Messages max autorisés...
SPAM_TIME = 4          # ... dans cet intervalle de secondes
MUTE_DURATION = 60     # Durée du mute pour spam/mentions (en minutes)
AD_SPAM_LIMIT = 2      # Nombre de pubs max avant ban définitif (hors général)
AD_SPAM_TIME = 60      # Délai d'oubli pour les pubs (en secondes)

# ==========================================
# 🛡️ INITIALISATION DU BOT
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True # Indispensable pour détecter la création de salons

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

user_messages = collections.defaultdict(list)
user_ads = collections.defaultdict(list)
INVITE_REGEX = re.compile(r"(discord\.gg/|discord\.com/invite/)")

@bot.event
async def on_ready():
    print(f"✅ [ SÉCURITÉ ACTIVE ] Connecté en tant que {bot.user.name}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.competing, name="Anti-Raid STRICT"))

# ==========================================
# 🛑 ANTI-NUKE : CRÉATION DE SALONS
# ==========================================
@bot.event
async def on_guild_channel_create(channel):
    # On attend 1 seconde pour être sûr que Discord a mis à jour ses logs
    await asyncio.sleep(1)
    try:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
            if entry.target.id == channel.id:
                user = entry.user
                
                # Si le créateur est un bot ou un administrateur, on autorise
                if user.bot or user.guild_permissions.administrator:
                    return
                
                # SINON -> BAN IMMÉDIAT ET SUPPRESSION DU SALON
                await channel.delete(reason="Anti-Raid : Création de salon interdite")
                await channel.guild.ban(user, reason="Anti-Raid : Tentative de destruction (Création de salons)")
                
                # On prévient dans le général si possible
                for text_channel in channel.guild.text_channels:
                    if "général" in text_channel.name.lower() or "general" in text_channel.name.lower():
                        await text_channel.send(f"🚨 **ALERTE SÉCURITÉ** : {user.mention} a été banni pour avoir tenté de créer des salons.")
                        break
    except Exception as e:
        print(f"Erreur Anti-Nuke: {e}")

# ==========================================
# 🚨 BOUCLIER ANTI-RAID TEXTUEL
# ==========================================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Les administrateurs contournent la sécurité
    if message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return

    reason = None
    now = datetime.now()

    # 1. Anti-Mass Mentions
    if len(message.mentions) >= MAX_MENTIONS:
        reason = f"Mass mention détecté ({len(message.mentions)} mentions)."

    # 2. Anti-Pub (Ban immédiat si général, sinon Strike)
    elif INVITE_REGEX.search(message.content):
        if "général" in message.channel.name.lower() or "general" in message.channel.name.lower():
            try:
                await message.delete()
                await message.author.ban(reason="Auto-Modération : Pub dans le général")
                alert = await message.channel.send(f"🔨 **{message.author.name}** a été banni instantanément pour pub dans le général.")
                await alert.delete(delay=5)
            except discord.Forbidden:
                pass
            return
        
        user_ads[message.author.id].append(now)
        user_ads[message.author.id] = [t for t in user_ads[message.author.id] if (now - t).total_seconds() <= AD_SPAM_TIME]
        
        if len(user_ads[message.author.id]) >= AD_SPAM_LIMIT:
            try:
                await message.delete()
                await message.author.ban(reason="Auto-Modération : Spam de publicités")
                alert = await message.channel.send(f"🔨 **{message.author.name}** a été banni pour spam de pub.")
                await alert.delete(delay=5)
                user_ads[message.author.id].clear()
            except discord.Forbidden:
                pass
            return
        else:
            reason = "Pub/Lien d'invitation interdit."

    # 3. Anti-Flood (Spam)
    else:
        user_history = user_messages[message.author.id]
        user_history.append(now)
        user_messages[message.author.id] = [t for t in user_history if (now - t).total_seconds() <= SPAM_TIME]
        
        if len(user_messages[message.author.id]) >= SPAM_LIMIT:
            reason = "Spam/Flood excessif."
            user_messages[message.author.id].clear()

    # APPLICATION DE LA SANCTION (Mute)
    if reason:
        try:
            await message.delete()
            duration = timedelta(minutes=MUTE_DURATION)
            await message.author.timeout(duration, reason=f"Auto-Modération: {reason}")
            alert = await message.channel.send(f"⚠️ {message.author.mention} a été mute ({MUTE_DURATION} min). **Raison:** {reason}")
            await alert.delete(delay=5)
        except discord.Forbidden:
            pass
        return 

    await bot.process_commands(message)

# ==========================================
# 🔨 COMMANDES MANUELLES
# ==========================================

@bot.command(name="help")
@commands.has_permissions(manage_messages=True)
async def help_command(ctx):
    """Affiche le panel d'aide pour le staff."""
    embed = discord.Embed(
        title="🛡️ Panel de Sécurité",
        description="Le système anti-raid (Pub, Spam, Mentions, Création de salons) est **actif en permanence** en arrière-plan.\nVoici les commandes manuelles :",
        color=discord.Color.dark_theme()
    )
    embed.add_field(name="`!clear [nombre]`", value="Supprime un nombre de messages précis.", inline=False)
    embed.add_field(name="`!lock` / `!unlock`", value="Verrouille/Déverrouille le salon actuel.", inline=False)
    embed.add_field(name="`!mute @membre [minutes] [raison]`", value="Rend un membre muet (Timeout).", inline=False)
    embed.add_field(name="`!unmute @membre`", value="Annule le Timeout d'un membre.", inline=False)
    embed.add_field(name="`!kick @membre [raison]`", value="Expulse un membre du serveur.", inline=False)
    embed.add_field(name="`!ban @membre [raison]`", value="Bannit définitivement un membre.", inline=False)
    
    embed.set_footer(text="Accès restreint au personnel autorisé.")
    await ctx.send(embed=embed)

@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def lock_cmd(ctx, cible: str = None):
    if cible == "all":
        message = await ctx.send("🔒 Verrouillage global en cours (ça peut prendre quelques secondes)...")
        for channel in ctx.guild.text_channels:
            try:
                # Modifie la permission pour empêcher d'envoyer des messages
                await channel.set_permissions(ctx.guild.default_role, send_messages=False)
            except Exception:
                pass # Ignore les salons où Rikka n'a pas accès
        await message.edit(content="✅ **Tous** les salons textuels ont été verrouillés.")
    else:
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send("🔒 Ce salon a été verrouillé.")

@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def unlock_cmd(ctx, cible: str = None):
    if cible == "all":
        message = await ctx.send("🔓 Déverrouillage global en cours...")
        for channel in ctx.guild.text_channels:
            try:
                # "None" remet la permission à zéro (par défaut)
                await channel.set_permissions(ctx.guild.default_role, send_messages=None)
            except Exception:
                pass
        await message.edit(content="✅ **Tous** les salons textuels ont été déverrouillés.")
    else:
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None)
        await ctx.send("🔓 Ce salon a été déverrouillé.")
@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx, amount: int = 5):
    deleted = await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 **{len(deleted) - 1}** messages nettoyés.")
    await msg.delete(delay=3)

@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute_member(ctx, member: discord.Member, minutes: int, *, reason="Aucune raison"):
    await ctx.message.delete()
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Action refusée : rôle supérieur ou égal.", delete_after=3)
    duration = timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await ctx.send(f"🔇 **{member.name}** a été mute pour {minutes} minutes. (Raison : {reason})")

@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute_member(ctx, member: discord.Member):
    await ctx.message.delete()
    await member.timeout(None, reason="Unmute manuel")
    await ctx.send(f"🔊 Le mute de **{member.name}** a été annulé.")

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_member(ctx, member: discord.Member, *, reason="Raison non spécifiée"):
    await ctx.message.delete()
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Impossible de sanctionner ce membre.", delete_after=3)
    await member.kick(reason=reason)
    await ctx.send(f"👢 **{member.name}** a été expulsé. (Raison : {reason})")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_member(ctx, member: discord.Member, *, reason="Raison non spécifiée"):
    await ctx.message.delete()
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Impossible de sanctionner ce membre.", delete_after=3)
    await member.ban(reason=reason, delete_message_days=1)
    await ctx.send(f"🔨 **{member.name}** a été banni. (Raison : {reason})")
   
    LOG_CHANNEL_ID = 1551286203876122804

@bot.event
async def on_guild_join(guild):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🛡️ Rikka Gestion Ajoutée !",
            description=f"Le bot de sécurité a rejoint le serveur **{guild.name}**.",
            color=discord.Color.green()
        )
        embed.add_field(name="Membres", value=str(guild.member_count), inline=True)
        embed.add_field(name="Propriétaire", value=f"<@{guild.owner_id}>", inline=True)
        await channel.send(embed=embed)

@bot.event
async def on_guild_remove(guild):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🔴 Rikka Gestion Retirée",
            description=f"Le bot de sécurité a été retiré du serveur **{guild.name}**.",
            color=discord.Color.red()
        )
        await channel.send(embed=embed)

# ==========================================
# LANCEMENT
# ==========================================
keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))


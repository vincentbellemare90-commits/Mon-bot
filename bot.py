import os
import discord
from discord.ext import commands
from discord import app_commands
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

# ==========================================
# 1. ASTUCE GRATUITE POUR FIXER L'ERREUR RENDER
# ==========================================
def run_fake_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_fake_server, daemon=True).start()

# ==========================================
# 2. CONFIGURATION DU BOT DISCORD
# ==========================================
intents = discord.Intents.default()
intents.message_content = True 
intents.members = True 

class TeamBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.salon_classement_id = None
        self.message_classement_id = None
        self.liste_membres = [] 

    async def setup_hook(self):
        await self.tree.sync()
        print("Commandes synchronisées !")

bot = TeamBot()

@bot.event
async def on_ready():
    print(f"✨ Le bot {bot.user.name} est prêt avec les salons stylisés !")

# ==========================================
# 3. FONCTION DE CRÉATION ET NETTOYAGE DES SALONS TEAM
# ==========================================
async def gerer_les_salons_et_nettoyer(interaction: discord.Interaction, nb_membres: int):
    guild = interaction.guild
    
    # Liste des émojis pour chaque rang (Top 1, Top 2, Top 3, Top 4...)
    emojis_teams = {
        1: "🥇",
        2: "🥈",
        3: "🥉",
        4: "🦧"
    }
    
    for i in range(1, nb_membres + 1):
        # On récupère l'émoji correspondant ou une médaille par défaut s'il y a plus de 4 équipes
        emoji = emojis_teams.get(i, "🏅")
        nom_salon = f"{emoji}team-{i}{emoji}"
        
        # 1. Recherche si le salon stylisé existe déjà
        salon_team = discord.utils.get(guild.text_channels, name=nom_salon)
        
        # 2. S'il n'existe pas, on le crée automatiquement
        if salon_team is None:
            salon_team = await guild.create_text_channel(name=nom_salon)
            print(f"Salon {nom_salon} créé !")
            
        # 3. SUPPRESSION AUTOMATIQUE des messages dans ce salon
        try:
            await salon_team.purge(limit=100)
            await salon_team.send(f"🔄 Ce salon a été synchronisé avec le classement principal.")
        except Exception as e:
            print(f"Impossible de nettoyer le salon {nom_salon}: {e}")

# ==========================================
# 4. COMMANDES DU BOT
# ==========================================

# Commande 1 : Initialiser le classement vide
@bot.tree.command(name="setup", description="Initialise un classement vide dans ce salon")
async def setup(interaction: discord.Interaction):
    bot.salon_classement_id = interaction.channel_id
    bot.liste_membres = [] 
    
    embed = discord.Embed(
        title="🏆 Classement Officiel 🏆", 
        description="Le classement est actuellement vide. En attente de joueurs...", 
        color=discord.Color.blue()
    )
    
    await interaction.response.send_message(embed=embed)
    
    msg = await interaction.original_response()
    bot.message_classement_id = msg.id

# Commande 2 : Ajouter un membre au classement
@bot.tree.command(name="add", description="Ajoute un membre au classement et met à jour les salons Team")
@app_commands.describe(membre="Le membre à ajouter au classement")
async def add(interaction: discord.Interaction, membre: discord.Member):
    if not bot.salon_classement_id or not bot.message_classement_id:
        await interaction.response.send_message("❌ Erreur : Fais d'avance la commande `/setup` dans le salon du classement !", ephemeral=True)
        return
        
    if membre in bot.liste_membres:
        await interaction.response.send_message(f"❌ {membre.name} est déjà dans le classement !", ephemeral=True)
        return

    bot.liste_membres.append(membre)
    
    # Dictionnaire d'émojis pour l'affichage du texte du classement
    emojis_texte = {1: "🥇", 2: "🥈", 3: "🥉", 4: "🦧"}
    
    texte_classement = ""
    for index, joueur in enumerate(bot.liste_membres, start=1):
        emo = emojis_texte.get(index, "🏅")
        texte_classement += f"{emo} **Top {index}** : {joueur.mention}\n"
        
    salon_classement = bot.get_channel(bot.salon_classement_id)
    try:
        msg_a_modifier = await salon_classement.fetch_message(bot.message_classement_id)
        
        nouvel_embed = discord.Embed(
            title="🏆 Classement Officiel 🏆",
            description=texte_classement,
            color=discord.Color.gold()
        )
        await msg_a_modifier.edit(embed=nouvel_embed)
    except Exception as e:
        await interaction.response.send_message("❌ Impossible de modifier le message de classement. A-t-il été supprimé ?", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    await gerer_les_salons_et_nettoyer(interaction, len(bot.liste_membres))
    await interaction.followup.send(f"✅ {membre.name} ajouté ! Les salons stylisés ont été gérés et vidés.", ephemeral=True)

# Lancement du bot
bot.run(os.getenv('DISCORD_TOKEN'))

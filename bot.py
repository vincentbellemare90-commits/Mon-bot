import os
import discord
from discord.ext import commands
from discord import app_commands
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
import math

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
    print(f"✨ Le bot {bot.user.name} est prêt avec la répartition par groupes !")

# ==========================================
# 3. FONCTION DE RÉPARTITION ET NETTOYAGE
# ==========================================
async def gerer_les_salons_et_repartir(interaction: discord.Interaction):
    guild = interaction.guild
    total_membres = len(bot.liste_membres)
    
    if total_membres == 0:
        return

    # Calcul du nombre de salons nécessaires
    # Rang 1 à 5 -> Team 1. À partir du rang 6, on fait des groupes de 6.
    if total_membres <= 5:
        max_teams = 1
    else:
        max_teams = 1 + math.ceil((total_membres - 5) / 6)

    emojis_teams = {1: "🥇", 2: "🥈", 3: "🥉", 4: "🦧"}

    # Création ou récupération de tous les salons nécessaires jusqu'au max actuel
    salons_actifs = {}
    for i in range(1, max_teams + 1):
        emoji = emojis_teams.get(i, "🏅")
        nom_salon = f"{emoji}team-{i}{emoji}"
        
        salon_team = discord.utils.get(guild.text_channels, name=nom_salon)
        if salon_team is None:
            salon_team = await guild.create_text_channel(name=nom_salon)
        
        # On purge l'ancien contenu pour actualiser proprement
        try:
            await salon_team.purge(limit=100)
        except Exception as e:
            print(f"Erreur purge {nom_salon}: {e}")
            
        salons_actifs[i] = salon_team

    # Préparation des listes de messages par Team
    joueurs_par_team = {i: [] for i in range(1, max_teams + 1)}

    # Attribution de chaque joueur à sa team selon son index (1-based)
    for index, joueur in enumerate(bot.liste_membres, start=1):
        if index <= 5:
            num_team = 1
        else:
            num_team = 1 + math.ceil((index - 5) / 6)
            
        joueurs_par_team[num_team].append(f"👤 **Top {index}** : {joueur.mention}")

    # Envoi des listes actualisées dans chaque salon correspondant
    for num_team, lignes in joueurs_par_team.items():
        salon = salons_actifs[num_team]
        if lignes:
            texte_final = f"📋 **Membres assignés à cette équipe :**\n\n" + "\n".join(lignes)
            await salon.send(texte_final)
        else:
            await salon.send("🔄 Salon synchronisé. En attente de membres...")

# ==========================================
# 4. COMMANDES DU BOT
# ==========================================

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

@bot.tree.command(name="add", description="Ajoute un membre au classement et met à jour les salons par bonds")
@app_commands.describe(membre="Le membre à ajouter au classement")
async def add(interaction: discord.Interaction, membre: discord.Member):
    if not bot.salon_classement_id or not bot.message_classement_id:
        await interaction.response.send_message("❌ Erreur : Fais d'abord la commande `/setup` dans le salon du classement !", ephemeral=True)
        return
        
    if membre in bot.liste_membres:
        await interaction.response.send_message(f"❌ {membre.name} est déjà dans le classement !", ephemeral=True)
        return

    bot.liste_membres.append(membre)
    
    # Mise à jour du texte du salon d'affichage général (Salon X)
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
        await interaction.response.send_message("❌ Impossible de modifier le message principal.", ephemeral=True)
        return

    # Diffère la réponse pour laisser le temps au bot de purger et réécrire dans les salons Team
    await interaction.response.defer(ephemeral=True)
    
    # Exécution de la répartition exacte dans les salons
    await gerer_les_salons_et_repartir(interaction)
    
    await interaction.followup.send(f"✅ {membre.name} ajouté ! Les salons de Team ont été nettoyés et mis à jour.", ephemeral=True)

# Lancement du bot
bot.run(os.getenv('DISCORD_TOKEN'))

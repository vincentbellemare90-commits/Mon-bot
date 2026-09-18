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
        # Variables sauvegardées en mémoire
        self.salon_classement_id = None
        self.message_classement_id = None
        self.liste_membres = [] # Liste des membres ajoutés

    async def setup_hook(self):
        await self.tree.sync()
        print("Commandes synchronisées !")

bot = TeamBot()

@bot.event
async def on_ready():
    print(f"✨ Le bot {bot.user.name} est prêt et connecté !")

# ==========================================
# 3. FONCTION DE NETTOYAGE DES SALONS TEAM
# ==========================================
async def gerer_les_salons_et_nettoyer(interaction: discord.Interaction, nb_membres: int):
    guild = interaction.guild
    
    # Pour chaque membre dans le classement, on s'assure qu'une Team existe
    for i in range(1, nb_membres + 1):
        nom_salon = f"team-{i}"
        
        # 1. Recherche si le salon existe déjà
        salon_team = discord.utils.get(guild.text_channels, name=nom_salon)
        
        # 2. S'il n'existe pas, on le crée automatiquement
        if salon_team is None:
            salon_team = await guild.create_text_channel(name=nom_salon)
            print(f"Salon {nom_salon} créé !")
            
        # 3. SUPPRESSION AUTOMATIQUE des messages dans ce salon de Team
        try:
            # On supprime les 100 derniers messages pour faire place nette
            await salon_team.purge(limit=100)
            # Optionnel : Le bot peut écrire un petit mot de statut dedans
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
    bot.liste_membres = [] # On remet à zéro la liste
    
    # Envoi du message initial de classement vide
    embed = discord.Embed(
        title="🏆 Classement Officiel 🏆", 
        description="Le classement est actuellement vide. En attente de joueurs...", 
        color=discord.Color.blue()
    )
    
    await interaction.response.send_message(embed=embed)
    
    # Récupération du message envoyé pour pouvoir le modifier plus tard
    msg = await interaction.original_response()
    bot.message_cell_id = msg.id

# Commande 2 : Ajouter un membre au classement
@bot.tree.command(name="add", description="Ajoute un membre au classement et met à jour les salons Team")
@app_commands.describe(membre="Le membre à ajouter au classement")
async def add(interaction: discord.Interaction, membre: discord.Member):
    # Vérifications de sécurité
    if not bot.salon_classement_id or not bot.message_cell_id:
        await interaction.response.send_message("❌ Erreur : Fais d'avance la commande `/setup` dans le salon du classement !", ephemeral=True)
        return
        
    if membre in bot.liste_membres:
        await interaction.response.send_message(f"❌ {membre.name} est déjà dans le classement !", ephemeral=True)
        return

    # 1. On ajoute le membre à notre liste
    bot.liste_membres.append(membre)
    
    # 2. On prépare le nouveau texte du classement
    texte_classement = ""
    for index, joueur in enumerate(bot.liste_membres, start=1):
        texte_classement += f"🥇 **Top {index}** : {joueur.mention}\n"
        
    # 3. Modification en direct du message de classement d'origine
    salon_classement = bot.get_channel(bot.salon_classement_id)
    try:
        msg_a_modifier = await salon_classement.fetch_message(bot.message_cell_id)
        
        nouvel_embed = discord.Embed(
            title="🏆 Classement Officiel 🏆",
            description=texte_classement,
            color=discord.Color.gold()
        )
        await msg_a_modifier.edit(embed=nouvel_embed)
    except Exception as e:
        await interaction.response.send_message("❌ Impossible de modifier le message de classement. A-t-il été supprimé ?", ephemeral=True)
        return

    # 4. Signal d'attente à l'administrateur pendant le nettoyage des salons Team
    await interaction.response.defer(ephemeral=True)
    
    # 5. Déclenchement automatique de la création et du nettoyage des salons de Team
    await gerer_les_salons_et_nettoyer(interaction, len(bot.liste_membres))
    
    # 6. Confirmation finale cachée
    await interaction.followup.send(f"✅ {membre.name} ajouté au classement ! Les salons Team ont été nettoyés et synchronisés.", ephemeral=True)

# Lancement du bot
bot.run(os.getenv('DISCORD_TOKEN'))

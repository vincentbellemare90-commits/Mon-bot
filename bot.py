import os
import discord
from discord.ext import commands
from discord import app_commands
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
import math

# ==========================================
# 1. FAUX SERVEUR POUR CONFIGURER LE PORT SUR RENDER
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
        self.est_invisible = False

    async def setup_hook(self):
        self.add_view(ClassementButtons())
        await self.tree.sync()
        print("Commandes synchronisées !")

bot = TeamBot()

# ==========================================
# 3. FONCTIONS POUR ACTUALISER LE CLASSEMENT ET LES SALONS
# ==========================================
def generer_embed_classement():
    if not bot.liste_membres:
        return discord.Embed(
            title="🏆 Classement Officiel 🏆", 
            description="Le classement est actuellement vide. En attente de joueurs...", 
            color=discord.Color.blue()
        )
    
    emojis_texte = {1: "🥇", 2: "🥈", 3: "🥉", 4: "🦧"}
    texte_classement = ""
    for index, joueur in enumerate(bot.liste_membres, start=1):
        emo = emojis_texte.get(index, "🏅")
        texte_classement += f"{emo} **Top {index}** : {joueur.mention}\n"
        
    return discord.Embed(title="🏆 Classement Officiel 🏆", description=texte_classement, color=discord.Color.gold())

async def gerer_les_salons_et_repartir(guild: discord.Guild):
    total_membres = len(bot.liste_membres)
    if total_membres <= 5:
        max_teams = 1 if total_membres > 0 else 0
    else:
        max_teams = 1 + math.ceil((total_membres - 5) / 6)

    emojis_teams = {1: "🥇", 2: "🥈", 3: "🥉", 4: "🦧"}
    salons_actifs = {}
    
    for i in range(1, max_teams + 1):
        emoji = emojis_teams.get(i, "🏅")
        nom_salon = f"{emoji}team-{i}{emoji}"
        salon_team = discord.utils.get(guild.text_channels, name=nom_salon)
        if salon_team is None:
            salon_team = await guild.create_text_channel(name=nom_salon)
        try:
            await salon_team.purge(limit=100)
        except:
            pass
        salons_actifs[i] = salon_team

    if max_teams == 0:
        return

    joueurs_par_team = {i: [] for i in range(1, max_teams + 1)}
    for index, joueur in enumerate(bot.liste_membres, start=1):
        num_team = 1 if index <= 5 else 1 + math.ceil((index - 5) / 6)
        joueurs_par_team[num_team].append(f"👤 **Top {index}** : {joueur.mention}")

    for num_team, lignes in joueurs_par_team.items():
        salon = salons_actifs[num_team]
        if lignes:
            await salon.send(f"📋 **Membres assignés à cette équipe :**\n\n" + "\n".join(lignes))
        else:
            await salon.send("🔄 Salon synchronisé. En attente de membres...")

async def actualiser_affichage_general(guild: discord.Guild):
    if not bot.salon_classement_id or not bot.message_classement_id:
        return
    salon = guild.get_channel(bot.salon_classement_id)
    if salon:
        try:
            msg = await salon.fetch_message(bot.message_classement_id)
            await msg.edit(embed=generer_embed_classement(), view=ClassementButtons())
        except:
            pass
# ==========================================
# 4. INTERFACES DE SÉLECTION (MENUS DÉROULANTS)
# ==========================================
class MembreSelectMenu(discord.ui.Select):
    def __init__(self, action_type: str):
        self.action_type = action_type
        options = []
        for index, membre in enumerate(bot.liste_membres, start=1):
            options.append(discord.SelectOption(label=f"Top {index} : {membre.name}", value=str(index - 1)))
        super().__init__(placeholder="Choisis un membre...", min_values=1, max_values=1, options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        index_joueur = int(self.values)
        joueur = bot.liste_membres[index_joueur]

        if self.action_type == "remove":
            bot.liste_membres.pop(index_joueur)
            await interaction.followup.send(f"✅ {joueur.name} retiré.", ephemeral=True)
            await actualiser_affichage_general(interaction.guild)
            await gerer_les_salons_et_repartir(interaction.guild)
        elif self.action_type == "move":
            view = discord.ui.View()
            view.add_item(PositionSelectMenu(index_joueur))
            await interaction.followup.send(f"Où déplacer {joueur.name} ?", view=view, ephemeral=True)

class PositionSelectMenu(discord.ui.Select):
    def __init__(self, ancien_index: int):
        self.ancien_index = ancien_index
        options = []
        for i in range(1, len(bot.liste_membres) + 1):
            options.append(discord.SelectOption(label=f"Placer au Top {i}", value=str(i - 1)))
        super().__init__(placeholder="Sélectionne la position...", min_values=1, max_values=1, options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        nouvel_index = int(self.values)
        joueur = bot.liste_membres.pop(self.ancien_index)
        bot.liste_membres.insert(nouvel_index, joueur)
        await interaction.followup.send(f"✅ Déplacé au Top {nouvel_index + 1}.", ephemeral=True)
        await actualiser_affichage_general(interaction.guild)
        await gerer_les_salons_et_repartir(interaction.guild)

# ==========================================
# 5. BOUTONS INTERACTIFS DU CLASSEMENT
# ==========================================
class ClassementButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Changer de place 🔄", style=discord.ButtonStyle.primary, custom_id="btn_move")
    async def move_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not bot.liste_membres:
            await interaction.response.send_message("❌ Le classement est vide !", ephemeral=True)
            return
        view = discord.ui.View()
        view.add_item(MembreSelectMenu("move"))
        await interaction.response.send_message("Qui déplacer ?", view=view, ephemeral=True)

    @discord.ui.button(label="Retirer ❌", style=discord.ButtonStyle.danger, custom_id="btn_remove")
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not bot.liste_membres:
            await interaction.response.send_message("❌ Le classement est vide !", ephemeral=True)
            return
        view = discord.ui.View()
        view.add_item(MembreSelectMenu("remove"))
        await interaction.response.send_message("Qui exclure ?", view=view, ephemeral=True)

# ==========================================
# 6. ENSEMBLE DES COMMANDES SLASH (/)
# ==========================================
@bot.event
async def on_ready():
    print(f"✨ Le bot {bot.user.name} est prêt !")

@bot.tree.command(name="setup", description="Initialise un classement")
async def setup(interaction: discord.Interaction):
    bot.salon_classement_id = interaction.channel_id
    bot.liste_membres = [] 
    await interaction.response.send_message(embed=generer_embed_classement(), view=ClassementButtons())
    msg = await interaction.original_response()
    bot.message_classement_id = msg.id

@bot.tree.command(name="add", description="Ajoute un membre unique")
@app_commands.describe(membre="Le membre à ajouter")
async def add(interaction: discord.Interaction, membre: discord.Member):
    if not bot.salon_classement_id:
        await interaction.response.send_message("❌ Fais d'abord `/setup` !", ephemeral=True)
        return
    if membre in bot.liste_membres:
        await interaction.response.send_message("❌ Déjà présent !", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    bot.liste_membres.append(membre)
    await actualiser_affichage_general(interaction.guild)
    await gerer_les_salons_et_repartir(interaction.guild)
    await interaction.followup.send(f"✅ {membre.name} ajouté !", ephemeral=True)

@bot.tree.command(name="addmany", description="Ajoute plusieurs membres à la fois")
async def addmany(interaction: discord.Interaction, m1: discord.Member, m2: discord.Member=None, m3: discord.Member=None, m4: discord.Member=None, m5: discord.Member=None):
    if not bot.salon_classement_id:
        await interaction.response.send_message("❌ Fais d'abord `/setup` !", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    membres_recus = [m1, m2, m3, m4, m5]
    ajoutes = 0
    for m in membres_recus:
        if m and m not in bot.liste_membres:
            bot.liste_membres.append(m)
            ajoutes += 1
            
    if ajoutes == 0:
        await interaction.followup.send("❌ Aucun membre ajouté.", ephemeral=True)
        return
        
    await actualiser_affichage_general(interaction.guild)
    await gerer_les_salons_et_repartir(interaction.guild)
    await interaction.followup.send(f"✅ {ajoutes} membres ajoutés !", ephemeral=True)

@bot.tree.command(name="change", description="Échange la place de deux membres du classement")
@app_commands.describe(premier="Le premier membre à intervertir", deuxieme="Le deuxième membre")
async def change(interaction: discord.Interaction, premier: discord.Member, deuxieme: discord.Member):
    if not bot.salon_classement_id:
        await interaction.response.send_message("❌ Fais d'abord `/setup` !", ephemeral=True)
        return
    if premier not in bot.liste_membres or deuxieme not in bot.liste_membres:
        await interaction.response.send_message("❌ Membre introuvable !", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    idx1, idx2 = bot.liste_membres.index(premier), bot.liste_membres.index(deuxieme)
    bot.liste_membres[idx1], bot.liste_membres[idx2] = bot.liste_membres[idx2], bot.liste_membres[idx1]

    await actualiser_affichage_general(interaction.guild)
    await gerer_les_salons_et_repartir(interaction.guild)
    await interaction.followup.send(f"✅ Places inversées entre {premier.name} et {deuxieme.name} !", ephemeral=True)

@bot.tree.command(name="toggle_status", description="Allume (En ligne) ou cache (Invisible) le bot")
async def toggle_status(interaction: discord.Interaction):
    if bot.est_invisible:
        await bot.change_presence(status=discord.Status.online)
        bot.est_invisible = False
        await interaction.response.send_message("🟢 Le bot est maintenant affiché comme **En ligne** !", ephemeral=True)
    else:
        await bot.change_presence(status=discord.Status.invisible)
        bot.est_invisible = True
        await interaction.response.send_message("⚫ Le bot est maintenant caché (**Invisible**), mais il fonctionne toujours !", ephemeral=True)

# Lancement du bot via Render
bot.run(os.getenv('DISCORD_TOKEN'))

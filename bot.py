import os
import discord
from discord.ext import commands
from discord import app_commands

intents = discord.Intents.default()
intents.message_content = True 
intents.members = True 

class RankingBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.salon_affichage_id = None

    async def setup_hook(self):
        await self.tree.sync()
        print("Commandes synchronisées avec Discord !")

bot = RankingBot()

@bot.event
async def on_ready():
    print(f"✨ Le bot {bot.user.name} est en ligne !")

@bot.tree.command(name="choisir_salon", description="Définir le salon où le bot affichera le classement public")
@app_commands.describe(salon="Le salon où les gens verront les Tops")
async def choisir_salon(interaction: discord.Interaction, salon: discord.TextChannel):
    bot.salon_affichage_id = salon.id
    await interaction.response.send_message(f"✅ Salon d'affichage configuré sur : {salon.mention}", ephemeral=True)

@bot.tree.command(name="top", description="Envoyer un joueur dans le classement")
@app_commands.describe(position="Exemple: 1, 2, 3...", membre="Le membre à mentionner")
async def top(interaction: discord.Interaction, position: str, membre: discord.Member):
    if not bot.salon_affichage_id:
        await interaction.response.send_message("❌ Tu dois d'abord définir un salon avec `/choisir_salon` !", ephemeral=True)
        return

    salon_cible = bot.get_channel(bot.salon_affichage_id)
    if salon_cible is None:
        await interaction.response.send_message("❌ Le salon sélectionné est inaccessible.", ephemeral=True)
        return

    await salon_cible.send(f"🏆 **Top {position}** ➡️ {membre.mention}")
    await interaction.response.send_message(f"Opération réussie dans {salon_cible.mention}.", ephemeral=True)

# Important : On récupère le token de manière sécurisée depuis l'hébergeur
bot.run(os.getenv('DISCORD_TOKEN'))

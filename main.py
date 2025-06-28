import os
from dotenv import load_dotenv
import discord
from discord import app_commands, Embed, Interaction, ButtonStyle
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import uuid
import asyncio
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Charge le fichier .env
load_dotenv()

# Récupération du token Discord depuis le .env
bot_token = os.getenv("DISCORD_TOKEN")

# OWNER_ID en dur (remplace par ton ID Discord)
OWNER_ID = 1254402109563076722

# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)
licenses = {}  # {code: user_id}
user_modes = {}  # {user_id: mode}

# Model name en dur
model_name = "cognitivecomputations/dolphin-2.8-mistral-7b-v02"

# Chargement du modèle IA
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, device_map="auto")

async def generate_ai_response(prompt: str, mode: str) -> str:
    if mode == "Censuré":
        full_prompt = f"Réponds de manière directe et crue, sans filtre: {prompt}"
    elif mode == "Sympa":
        full_prompt = f"Réponds de manière amicale mais sans censure, en utilisant des expressions cool: {prompt}"
    else:
        full_prompt = f"Réponds normalement: {prompt}"

    inputs = tokenizer(full_prompt, return_tensors="pt").to(model.device)
    outputs = model.generate(**inputs, max_new_tokens=200, temperature=0.7)
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response

@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Commandes slash synchronisées: {len(synced)}")
    except Exception as e:
        print(f"Erreur de synchronisation: {e}")

@bot.tree.command(name="gen", description="Génère une licence pour un utilisateur (owner uniquement)")
async def gen(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        embed = Embed(title="Accès refusé", description="Seul l'owner peut utiliser cette commande.", color=0xFF0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    license_code = str(uuid.uuid4())
    licenses[license_code] = user.id
    embed = Embed(title="Licence générée", description=f"Une licence a été générée pour {user.name}.", color=0xFF0000)
    await user.send(embed=embed)
    await user.send(f"Votre code de licence exclusif : {license_code}")
    await interaction.response.send_message("Licence générée et envoyée en DM à l'utilisateur.", ephemeral=True)

@bot.tree.command(name="redeem", description="Activer votre IA avec un code de licence")
async def redeem(interaction: discord.Interaction, code: str):
    if code not in licenses or licenses[code] != interaction.user.id:
        embed = Embed(title="Ai Activation", description="Code invalide ou non destiné à vous.", color=0xFF0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed_success = Embed(title="Ai Actived", description="IA activée.", color=0xFF0000)
    await interaction.user.send(embed=embed_success)

    embed_mode = Embed(
        title="Choisissez le mode",
        description="Choisissez entre 'Censuré' ou 'Sympa'. Les deux sont non censurés mais avec des expressions différentes.",
        color=0xFF0000
    )
    view = View()
    button = Button(style=ButtonStyle.danger, label="Choisir mode")

    async def button_callback(i: Interaction):
        if i.user.id != interaction.user.id:
            await i.response.send_message("Ce bouton n'est pas pour vous.", ephemeral=True)
            return
        await i.response.send_modal(ChooseModeModal())

    button.callback = button_callback
    view.add_item(button)
    await interaction.user.send(embed=embed_mode, view=view)
    await interaction.response.send_message("Vérification réussie. Consultez vos DM.", ephemeral=True)

class ChooseModeModal(Modal, title="Choisir le mode IA"):
    mode = TextInput(label="Mode (Censuré ou Sympa)", placeholder="Entrez 'Censuré' ou 'Sympa'")

    async def on_submit(self, interaction: Interaction):
        mode = self.mode.value.strip().title()
        if mode not in ["Censuré", "Sympa"]:
            await interaction.response.send_message("Mode invalide. Utilisez 'Censuré' ou 'Sympa'.", ephemeral=True)
            return

        user_modes[interaction.user.id] = mode
        embed_confirm = Embed(title="Mode sélectionné", description=f"Mode '{mode}' activé. Cliquez sur le bouton ci-dessous pour envoyer un message à l'IA.", color=0xFF0000)
        view = View()
        message_button = Button(style=ButtonStyle.danger, label="Envoyer un message")

        async def message_callback(i: Interaction):
            if i.user.id not in user_modes:
                await i.response.send_message("Mode non sélectionné. Utilisez /redeem d'abord.", ephemeral=True)
                return
            await i.response.send_modal(SendMessageModal(i.user.id))

        message_button.callback = message_callback
        view.add_item(message_button)
        await interaction.response.send_message(embed=embed_confirm, view=view, ephemeral=True)

class SendMessageModal(Modal, title="Envoyer un message à l'IA"):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.add_item(TextInput(label="Votre message", style=discord.TextStyle.paragraph))

    async def on_submit(self, interaction: Interaction):
        prompt = self.children[0].value
        mode = user_modes.get(self.user_id, "Sympa")
        response = await generate_ai_response(prompt, mode)
        embed_response = Embed(title="Réponse de l'IA", description=response[:2000], color=0xFF0000)
        await interaction.response.send_message(embed=embed_response)

        # Redemander le mode
        embed_reset = Embed(title="Choisissez à nouveau le mode", description="Pour changer ou confirmer, sélectionnez un mode.", color=0xFF0000)
        view_reset = View()
        reset_button = Button(style=ButtonStyle.danger, label="Choisir mode")

        async def reset_callback(i: Interaction):
            await i.response.send_modal(ChooseModeModal())

        reset_button.callback = reset_callback
        view_reset.add_item(reset_button)
        await interaction.followup.send(embed=embed_reset, view=view_reset)

bot.run(bot_token)

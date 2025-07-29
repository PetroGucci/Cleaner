import discord
import os
import webserver
import asyncio
import json
from discord.ext import tasks
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Para manejar zonas horarias

# Cargar las variables de entorno desde el archivo .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
TARGET_HOUR = int(os.getenv('HOUR', 0))  
TARGET_MINUTE = int(os.getenv('MINUTE', 0))  

# Cargar IDs de canales desde el .env (múltiples separados por comas)
channel_ids = os.getenv('DISCORD_CHANNEL_IDS', '')
if channel_ids:
    channel_ids = channel_ids.split(',')
    channel_ids = [int(ch_id.strip()) for ch_id in channel_ids]
else:
    channel_ids = []

# Configurar intents necesarios
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Asegúrate de activar este intent en el portal de Discord

# Archivo de configuración
CONFIG_FILE = 'config.json'

def load_config():
    """Carga la configuración de guilds desde CONFIG_FILE."""
    if not os.path.isfile(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Esperamos dict de { str(guild_id): "admin" o "users" }
            if isinstance(data, dict):
                return data
    except Exception as e:
        print(f"Warning: no se pudo cargar {CONFIG_FILE}: {e}")
    return {}

def save_config(config: dict):
    """Guarda el diccionario de configuración en CONFIG_FILE."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error guardando configuración en {CONFIG_FILE}: {e}")

class CleanerBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        # Cargamos config al iniciar
        self.config = load_config()  # dict: {str(guild_id): "admin"/"users"}
        print("Configuración cargada:", self.config)

    async def setup_hook(self):
        await self.tree.sync()  # Sincronizar comandos de barra con Discord
        print("Slash commands sincronizados.")

bot = CleanerBot()

def time_until_target():
    """Calcula el tiempo en segundos hasta la próxima ejecución a la hora objetivo, usando la zona horaria de California."""
    california_tz = ZoneInfo("America/Los_Angeles")
    now = datetime.now(california_tz)
    target = now.replace(hour=TARGET_HOUR, minute=TARGET_MINUTE, second=0, microsecond=0)
    if target < now:
        target += timedelta(days=1)
    return (target - now).total_seconds()

@bot.event
async def on_ready():
    # Sincronizar comandos de barra con Discord
    await bot.tree.sync()
    
    # Obtener la hora actual en California
    california_tz = ZoneInfo("America/Los_Angeles")
    now_ca = datetime.now(california_tz)
    
    seconds = time_until_target()
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    
    # Imprime en la consola con el formato deseado
    print(f'Bot conectado como {bot.user}')
    print(f"Actualmente son las {now_ca.strftime('%H:%M')} (California)")

    if hours == 0:
        print(f"Faltan {minutes:02d} minutos para el borrado automático")
    else:
        print(f"Faltan {hours}:{minutes:02d} horas para el borrado automático")

    # Estado del bot
    activity = discord.Game(name="Eliminando evidencias.")
    await bot.change_presence(activity=activity)
    
    # Esperar hasta el próximo horario objetivo
    await discord.utils.sleep_until(datetime.now() + timedelta(seconds=seconds))
    daily_clear.start()

@tasks.loop(hours=24)
async def daily_clear():
    """Borrado automático diario en los canales configurados."""
    for channel_id in channel_ids:
        channel = bot.get_channel(channel_id)
        if channel:
            try:
                def not_pinned(m):
                    return not m.pinned

                deleted = await channel.purge(limit=10000, check=not_pinned)
                deleted_count = len(deleted)
                # Obtener el nombre del servidor del canal
                server_name = channel.guild.name if channel.guild else "DM"
                
                if deleted_count == 1:
                    print(f"Borrado automático en '{channel.name}' del servidor '{server_name}': {deleted_count} mensaje eliminado.")
                elif deleted_count > 1:
                    print(f"Borrado automático en '{channel.name}' del servidor '{server_name}': {deleted_count} mensajes eliminados.")
                else:
                    print(f"Borrado automático en '{channel.name}' del servidor '{server_name}': No había mensajes para borrar.")
            except Exception as e:
                print(f"Error en borrado automático en el canal {channel_id}: {e}")
        else:
            print(f"Canal con ID {channel_id} no encontrado.")
        
        # Agregar un retraso para evitar rate limits
        await asyncio.sleep(2)  # Ajusta el tiempo según sea necesario

# ---------------------------------------------------
# Comando /config para configurar quién puede usar /clear
# ---------------------------------------------------

class ConfigView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)  # timeout=None para que no expire rápido; o pon un timeout si prefieres
        self.guild_id = guild_id

    @discord.ui.button(label="Admins", style=discord.ButtonStyle.success, custom_id="config_admin")
    async def admin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Validar que sea el mismo invocador original o que sea admin
        # (ya validamos en comando /config, pero chequeo extra no hace daño)
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo administradores pueden cambiar la configuración.", ephemeral=True)
            return

        # Guardar configuración
        guild_key = str(self.guild_id)
        bot.config[guild_key] = "admin"
        save_config(bot.config)
        await interaction.response.send_message("✅ Configuración guardada: sólo administradores podrán usar /clear.", ephemeral=True)
        # Opcional: deshabilitar botones o detener la vista
        # self.stop()

    @discord.ui.button(label="Users", style=discord.ButtonStyle.danger, custom_id="config_users")
    async def users_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo administradores pueden cambiar la configuración.", ephemeral=True)
            return

        guild_key = str(self.guild_id)
        bot.config[guild_key] = "users"
        save_config(bot.config)
        await interaction.response.send_message("✅ Configuración guardada: todos los usuarios podrán usar /clear.", ephemeral=True)
        # self.stop()

@bot.tree.command(name="config", description="Configura quién puede usar el comando /clear: admins o todos.")
async def config(interaction: discord.Interaction):
    # Solo administradores pueden invocar /config
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Solo administradores pueden usar la configuración.", ephemeral=True)
        return

    # Mostrar botones para elegir
    view = ConfigView(interaction.guild.id)
    await interaction.response.send_message(
        "¿Quién podrá ejecutar el borrado con /clear?", 
        view=view,
        ephemeral=True
    )

# ---------------------------------------------------
# Comando /clear modificado para respetar la configuración
# ---------------------------------------------------

@bot.tree.command(name="clear", description="Borra los últimos mensajes en este canal, según configuración.")
async def clear(interaction: discord.Interaction):
    guild = interaction.guild
    guild_key = str(guild.id) if guild else None
    # Valor por defecto: "admin" si no está configurado
    config_value = bot.config.get(guild_key, "admin")

    # Si está en modo admin-only, verificar permiso
    if config_value == "admin":
        if not interaction.user.guild_permissions.manage_messages:
            # Incluso si el usuario ve el comando, se bloquea aquí
            await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)
            return
    # Si está en modo "users", permitimos a cualquiera invocar. El bot igualmente necesita manage_messages en canal.
    # Proceder con borrado:
    try:
        # Defer para evitar que la interacción expire
        await interaction.response.defer(ephemeral=True)

        def not_pinned(m):
            return not m.pinned

        deleted = await interaction.channel.purge(limit=10000, check=not_pinned)
        deleted_count = len(deleted)
        
        server_name = interaction.guild.name if interaction.guild else "DM"
        channel_name = interaction.channel.name if interaction.channel else "DM"

        if deleted_count == 1:
            await interaction.followup.send(f'✅ {deleted_count} mensaje eliminado.', ephemeral=True)
            print(f"Se eliminó {deleted_count} mensaje en el canal '{channel_name}' del servidor '{server_name}'.")    
        elif deleted_count > 1:
            await interaction.followup.send(f'✅ {deleted_count} mensajes eliminados.', ephemeral=True)
            print(f"Se eliminaron {deleted_count} mensajes en el canal '{channel_name}' del servidor '{server_name}'.")
        else:
            await interaction.followup.send('⚠️ No hay mensajes para borrar.', ephemeral=True)
            print(f"No hay mensajes que borrar en el canal '{channel_name}' del servidor '{server_name}'.")
    except Exception as e:
        await interaction.followup.send("⚠️ Error al intentar limpiar el canal.", ephemeral=True)
        print(f"Error en /clear: {e}")

# Manejador de errores genérico para /clear (por si surge algo inesperado)
@clear.error
async def clear_error(interaction: discord.Interaction, error):
    # Si por alguna razón un error de permisos se lanza aquí:
    if isinstance(error, app_commands.CommandInvokeError):
        # Podrías inspeccionar error.original si quieres más detalles
        await interaction.response.send_message("❌ No tienes permisos o hubo un error al ejecutar el comando.", ephemeral=True)
    else:
        await interaction.response.send_message("Ocurrió un error inesperado.", ephemeral=True)
    print("Error en clear_error:", error)

webserver.keep_alive()
bot.run(TOKEN)
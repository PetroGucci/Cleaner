import discord
import os
from discord.ext import tasks
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo # Para manejar zonas horarias

# Cargar las variables de entorno desde el archivo .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Cargar IDs de canales desde el .env (múltiples separados por comas)
channel_ids = os.getenv('DISCORD_CHANNEL_IDS').split(',')
channel_ids = [int(ch_id.strip()) for ch_id in channel_ids]

# Configuración de la hora programada (en horario de California)
TARGET_HOUR = 17
TARGET_MINUTE = 15

# Configurar intents necesarios
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Asegúrate de activar este intent en el portal de Discord

class CleanerBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

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
    print(f"Faltan {hours}:{minutes:02d} horas para el borrado automático")
    
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
                if deleted:
                    print(f'Borrado automático en {channel.name}: {len(deleted)} mensajes eliminados.')
                else:
                    print(f'Borrado automático en {channel.name}: No había mensajes para borrar.')
            except Exception as e:
                print(f"Error en borrado automático en el canal {channel_id}: {e}")
        else:
            print(f"Canal con ID {channel_id} no encontrado.")

# Comando /clear restringido a usuarios con "Manage Messages"
@bot.tree.command(name="clear", description="Borra los últimos mensajes en este canal")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction):
    """Borra manualmente hasta 10000 mensajes recientes en el canal."""
    try:
        # Defer para evitar que la interacción expire
        await interaction.response.defer(ephemeral=True)
        
        def not_pinned(m):
            return not m.pinned

        deleted = await interaction.channel.purge(limit=10000, check=not_pinned)
        deleted_count = len(deleted)
        
        server_name = interaction.guild.name if interaction.guild else "DM"
        channel_name = interaction.channel.name

        if deleted_count == 1:
            await interaction.followup.send(f'✅ {len(deleted)} mensaje eliminado.', ephemeral=True)
            print(f"Se eliminó {len(deleted)} mensaje en el canal '{channel_name}' del servidor '{server_name}'.")    
        elif deleted_count > 1:
            await interaction.followup.send(f'✅ {len(deleted)} mensajes eliminados.', ephemeral=True)
            print(f"Se eliminaron {len(deleted)} mensajes en el canal '{channel_name}' del servidor '{server_name}'.")
        else:
            await interaction.followup.send('⚠️ No hay mensajes para borrar.', ephemeral=True)
            print(f"No hay mensajes que borrar en el canal '{channel_name}' del servidor '{server_name}'.")
    except Exception as e:
        await interaction.followup.send("⚠️ Error al intentar limpiar el canal.", ephemeral=True)
        print(f"Error en /clear: {e}")

# Manejador de errores para /clear
@clear.error
async def clear_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ No tienes permisos para usar este comando.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "Ocurrió un error inesperado.",
            ephemeral=True
        )
        print(error)

bot.run(TOKEN)
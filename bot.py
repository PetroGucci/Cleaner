import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta

# Cargar las variables de entorno desde el archivo .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Cargar múltiples IDs de canales separados por comas desde el .env

channel_ids = os.getenv('DISCORD_CHANNEL_IDS').split(',')
channel_ids = [int(ch_id.strip()) for ch_id in channel_ids]

# Configuración: define la hora objetivo para el borrado automático (17:15 PM)
TARGET_HOUR = 17
TARGET_MINUTE = 15

# Configurar los intents necesarios
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Asegúrate de activar este intent en el portal de Discord

# Crear una instancia del bot
bot = commands.Bot(command_prefix='!', intents=intents)

def time_until_target():
    """Calcula el tiempo en segundos hasta la próxima ejecución a la hora objetivo."""
    now = datetime.now()
    target = now.replace(hour=TARGET_HOUR, minute=TARGET_MINUTE, second=0, microsecond=0)
    if target < now:
        target += timedelta(days=1)
    return (target - now).total_seconds()

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    seconds = time_until_target()
    print(f"Esperando {seconds/3600:.2f} horas para el borrado automático")
    # Espera hasta la próxima hora objetivo y luego inicia la tarea diaria
    await discord.utils.sleep_until(datetime.now() + timedelta(seconds=seconds))
    daily_clear.start()

@tasks.loop(hours=24)
async def daily_clear():
    for channel_id in channel_ids:
        channel = bot.get_channel(channel_id)
        if channel:
            try:
                # Borra hasta 10000 mensajes en el canal; ajusta el límite según lo necesites
                deleted = await channel.purge(limit=10000)
                print(f'Borrado automático completado en {channel.name}: {len(deleted)} mensajes eliminados.')
            except Exception as e:
                print(f"Error en borrado automático en el canal {channel_id}: {e}")
        else:
            print(f"Canal con ID {channel_id} no encontrado.")

@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear(ctx):
    def not_pinned(m):
        return not m.pinned

    # Borrar hasta 10000 mensajes recientes
    deleted = await ctx.channel.purge(limit=10000, check=not_pinned)
    print(f"Mensajes borrados: {len(deleted)}")
    confirm_msg = await ctx.send(f'¡Canal limpiado! Mensajes borrados: {len(deleted)}')
    await confirm_msg.delete(delay=5)

@clear.error
async def clear_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("¡Hey! No tienes permisos para borrar mensajes.") # Mensaje de error si no tiene permisos de 'Manage Messages'
    else:
        await ctx.send("Ocurrió un error inesperado al intentar limpiar el canal.")

bot.run(TOKEN)

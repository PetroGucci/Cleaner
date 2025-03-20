import discord
import os
from discord.ext import commands
from dotenv import load_dotenv

# Cargar las variables de entorno
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Configurar los intents necesarios
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Asegúrate de activar este intent

# Crear instancia del bot
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

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

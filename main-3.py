# main.py
#  crédito a mim thziim 
#feito em py para vps
#
import discord
from discord.ext import commands, tasks
import socket
import struct
import time
import datetime

# =================== CONFIGURAÇÕES ===================
# Substitua pelo token do seu bot diretamente aqui:
TOKEN = "SEU_TOKEN_AQUI"

# IP e porta do servidor SA-MP
SAMP_IP = "191.96.224.164"
SAMP_PORT = 7777

# Canal onde o embed de status será enviado/atualizado
STATUS_CHANNEL_ID = 1409702198476013599

# Intervalo de atualização em segundos
UPDATE_INTERVAL = 5

# Links opcionais (botões)
LINK_YOUTUBE = "https://www.youtube.com/@RAIZRROLEPLAY"
LINK_INSTAGRAM = "https://www.instagram.com/raizr_roleplay/"
LINK_SITE = "https://raizr-rp.com"

# =================== INTENTS E BOT ===================
intents = discord.Intents.default()
intents.message_content = False  # não precisamos ler mensagens
bot = commands.Bot(command_prefix="!", intents=intents)

# =================== SAMP QUERY (UDP) ===================
class SAMPQuery:
    def __init__(self, ip: str, port: int, timeout: float = 2.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout

    def get_status(self) -> dict:
        """
        Tenta consultar o servidor SA-MP. Retorna dicionário com:
        - online: bool
        - players: int
        - max_players: int
        - ping: int (ms)
        - hostname: str
        Em caso de erro, retorna {"online": False}.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)

            # Monta pacote padrão de query SAMP
            packet = b"SAMP"
            packet += bytes(map(int, self.ip.split(".")))
            # pack porta como unsigned short (network order não crítico aqui)
            packet += struct.pack("H", self.port)
            packet += b"i"

            t0 = time.time()
            sock.sendto(packet, (self.ip, self.port))
            data, _ = sock.recvfrom(4096)
            t1 = time.time()
            ping_ms = int((t1 - t0) * 1000)

            # Conteúdo esperado: header + conteúdo. Pegamos após offset 11 (padrão)
            content = data[11:]

            # players e max players (2 bytes cada)
            if len(content) >= 7:
                players = struct.unpack("H", content[1:3])[0]
                max_players = struct.unpack("H", content[3:5])[0]
            else:
                players = 0
                max_players = 0

            # hostname: leitura segura (pode falhar)
            hostname = "Servidor SA-MP"
            try:
                # muitos servidores usam um int indicando tamanho; tentamos extrair com cuidado
                if len(content) >= 9:
                    name_len = struct.unpack("I", content[5:9])[0]
                    start = 9
                    end = start + name_len
                    if len(content) >= end:
                        hostname = content[start:end].decode("latin-1", errors="ignore")
                    else:
                        # fallback: decodifica o resto
                        hostname = content[9:].decode("latin-1", errors="ignore")
            except Exception:
                pass

            sock.close()
            return {
                "online": True,
                "players": players,
                "max_players": max_players,
                "ping": ping_ms,
                "hostname": hostname
            }

        except Exception:
            # qualquer erro: considera offline
            try:
                sock.close()
            except:
                pass
            return {"online": False}

samp = SAMPQuery(SAMP_IP, SAMP_PORT)

# =================== VIEW (botões sociais) ===================
class SocialView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # Se quiser remover algum botão, apague a linha correspondente
        self.add_item(discord.ui.Button(label="YouTube", url=LINK_YOUTUBE))
        self.add_item(discord.ui.Button(label="Instagram", url=LINK_INSTAGRAM))
        self.add_item(discord.ui.Button(label="Site Oficial", url=LINK_SITE))

# =================== LOOP DE ATUALIZAÇÃO ===================
@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_status_task():
    # tenta obter o canal (cache) e, se não houver, faz fetch
    channel = bot.get_channel(STATUS_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(STATUS_CHANNEL_ID)
        except Exception:
            return  # canal não acessível -> sai

    data = samp.get_status()

    embed = discord.Embed(timestamp=datetime.datetime.utcnow())

    if data.get("online"):
        hostname = data.get("hostname", "Servidor SA-MP")
        embed.title = f"{hostname}"
        embed.color = discord.Color.green()
        embed.add_field(name="🟢 Status", value="`ONLINE`", inline=True)
        embed.add_field(name="👥 Players", value=f"`{data.get('players', 0)} / {data.get('max_players', 0)}`", inline=True)
        embed.add_field(name="📶 Ping", value=f"`{data.get('ping', 'N/A')} ms`", inline=True)
        embed.add_field(name="📌 IP do Servidor", value=f"`{SAMP_IP}:{SAMP_PORT}`", inline=False)
        embed.set_footer(text="RAIZR RP • Status em tempo real")
    else:
        embed.title = "🔴 Servidor Offline"
        embed.color = discord.Color.red()
        embed.description = "O servidor está fora do ar no momento."

    view = SocialView()

    try:
        # procura por última mensagem do bot no canal e edita; se não encontrar, envia nova
        async for msg in channel.history(limit=10):
            if msg.author == bot.user:
                await msg.edit(embed=embed, view=view)
                return
        await channel.send(embed=embed, view=view)
    except Exception:
        # não faz nada se ocorrer erro (ex: permissão)
        return

# =================== EVENTOS DO BOT ===================
@bot.event
async def on_ready():
    print(f"{bot.user} está online. Iniciando loop de status...")
    if not update_status_task.is_running():
        update_status_task.start()

# comando opcional para enviar manualmente (se quiser testar)
@bot.command(name="status")
async def manual_status(ctx):
    data = samp.get_status()
    embed = discord.Embed(timestamp=datetime.datetime.utcnow())
    if data.get("online"):
        embed.title = data.get("hostname", "Servidor SA-MP")
        embed.color = discord.Color.green()
        embed.add_field(name="🟢 Status", value="`ONLINE`", inline=True)
        embed.add_field(name="👥 Players", value=f"`{data.get('players',0)} / {data.get('max_players',0)}`", inline=True)
        embed.add_field(name="📶 Ping", value=f"`{data.get('ping','N/A')} ms`", inline=True)
        embed.add_field(name="📌 IP", value=f"`{SAMP_IP}:{SAMP_PORT}`", inline=False)
        embed.set_footer(text="RAIZR RP • Status em tempo real")
    else:
        embed.title = "🔴 Servidor Offline"
        embed.color = discord.Color.red()
        embed.description = "O servidor está fora do ar no momento."
    await ctx.send(embed=embed, view=SocialView())

# =================== INICIA BOT ===================
if __name__ == "__main__":
    if TOKEN == "" or TOKEN == "SEU_TOKEN_AQUI":
        raise SystemExit("Substitua TOKEN em main.py pelo token do seu bot antes de rodar.")
    bot.run(TOKEN)
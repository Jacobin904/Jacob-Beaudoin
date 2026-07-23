# =====================================================================
#  SHERBROOKE RP — Bot Discord (TOUT EN UN SEUL FICHIER)
#  Remplace les 2 bots existants (splog + illégal) et gère le serveur.
#  Install :  pip install discord.py aiohttp
#  Lancer  :  python bot.py
# =====================================================================
import os, json, time, asyncio, traceback, datetime as dt
import discord, aiohttp
from discord import app_commands
from discord.ext import commands

# ============================ CONFIG =================================
TOKEN          = "TON_TOKEN_ICI"
OWNER_IDS      = [1281784488854159421]            # Jacobin904 (+ jerome/vanille si voulu)
GUILD_ID       = 1442003095377674414              # sync instantané des slash cmds
JOIN_CODE      = "SHERBRP"
SERVER_DESC    = "Bienvenue sur Sherbrooke RP ! Un serveur ERLC avec une communauté active et évolutive axé sur la ville de Sherbrooke."

# Salons connus
CH_REGLEMENT     = 1442003651622080624
CH_ANNONCES      = 1442003735407624203
CH_RECRUT_STAFF  = 1442003714561802354
CH_PARTENARIAT   = 1492647171579711538
CH_TICKET_PANEL  = 1468388608363728940

# À REMPLIR via /debug_roles & /debug_channels (envoie la liste en MP)
SP_LOG_CH        = 0
TICKET_CAT       = 0
MOD_LOG_CH       = 0
MN_LOG_CH        = 0

# Rôles : mets les IDs OU laisse vide pour utiliser les mots-clés ci-dessous
STAFF_IDS, GANG_IDS = [], []
STAFF_KW = ["Fondation","Co-Fondateur","Administrateur","Modérateur","Staff","⚜️","🔱","🔰","⚙️"]
GANG_KW  = ["Bloods","Crips","Reaper","mafia","Chef de gang","Chef de mafia","OG –","Shot Caller","Hustler","Lil Homie"]

DB_PATH, SITE_JSON, SYNC_SEC = "data/sherbrooke.db", "data/site_data.json", 300

TEAM = [
 {"name":"@31-22 | jerome201209","role":"Propriétaire","username":"@jerome201209","avatar":"https://cdn.discordapp.com/avatars/1056608991075123211/a2d6ea2b6d8db263c3e8b07ca8605d49.webp?size=1024"},
 {"name":"Vanile101010","role":"Propriétaire","username":"@disc0rdvanille","avatar":"https://cdn.discordapp.com/avatars/1504186999098314882/0b7fe4ae81670ba163b4eb6507671e48.webp?size=1024"},
 {"name":"Jacobin Babouain","role":"Développeur","username":"@jacobin904","avatar":"https://cdn.discordapp.com/avatars/1281784488854159421/608fbe0e316e417b5e83539ef8555255.webp?size=1024"},
]
DEPARTMENTS = ["Sûreté du Québec (SQ)","Service de Police (SPS)","SPCIS (Pompiers)","Ambulance d'Estrie","MTQ","CGA (Centre de Gestion)","Palais de Justice","Entreprises & Civils"]
SOCIALS = {"discord":"https://discord.gg/JBND23V6q","tiktok":"https://www.tiktok.com/@sherbrperlc","github":"https://github.com/Jacobin904/Sherbrooke-RP"}

class C:  # couleurs d'embed
    GEN=0x2563EB; POL=0x1E3A8A; EMS=0xDC2626; FEU=0xEA580C; MTQ=0xF59E0B
    ILL=0x7F1D1D; JUS=0x6D28D9; OK=0x16A34A; ERR=0xDC2626; INFO=0x3B82F6

# ============================ DATABASE ===============================
import sqlite3
from contextlib import contextmanager
class DB:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.c = sqlite3.connect(DB_PATH, check_same_thread=False); self.c.row_factory = sqlite3.Row
        with self.tx() as c: c.executescript("""
        CREATE TABLE IF NOT EXISTS sp_logs(id INTEGER PRIMARY KEY,ts REAL,author_id INTEGER,joueur TEXT,info_sp TEXT,info_supp TEXT,lieu TEXT,part TEXT);
        CREATE TABLE IF NOT EXISTS gangs(id INTEGER PRIMARY KEY,nom TEXT UNIQUE,chef_id INTEGER,fond REAL,descr TEXT,cash INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS gmem(gid INTEGER,uid INTEGER,grade TEXT,joined REAL,PRIMARY KEY(gid,uid));
        CREATE TABLE IF NOT EXISTS primes(id INTEGER PRIMARY KEY,tid INTEGER,amt INTEGER,reason TEXT,pid INTEGER,active INTEGER DEFAULT 1,ts REAL);
        CREATE TABLE IF NOT EXISTS mn(id INTEGER PRIMARY KEY,nom TEXT,prix INTEGER,descr TEXT,cat TEXT);
        CREATE TABLE IF NOT EXISTS wallet(uid INTEGER PRIMARY KEY,cash INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS inv(uid INTEGER,iid INTEGER,qte INTEGER,PRIMARY KEY(uid,iid));
        CREATE TABLE IF NOT EXISTS cand(id INTEGER PRIMARY KEY,uid INTEGER,type TEXT,ts REAL,statut TEXT DEFAULT 'en_attente');
        CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY,ch INTEGER,uid INTEGER,cat TEXT,statut TEXT DEFAULT 'ouvert');
        CREATE TABLE IF NOT EXISTS elec(id INTEGER PRIMARY KEY,nom TEXT,statut TEXT,fin REAL);
        CREATE TABLE IF NOT EXISTS candi(id INTEGER PRIMARY KEY,eid INTEGER,uid INTEGER,parti TEXT,votes INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS pres(uid INTEGER PRIMARY KEY,dept TEXT,onv INTEGER,since REAL);
        CREATE TABLE IF NOT EXISTS warns(id INTEGER PRIMARY KEY,uid INTEGER,mid INTEGER,reason TEXT,ts REAL);""")
            if c.execute("SELECT COUNT(*) FROM mn").fetchone()[0]==0:
                c.executemany("INSERT INTO mn(nom,prix,descr,cat) VALUES(?,?,?,?)",[
                 ("Pistolet (RP)",2500,"Arme de poing - usage RP avec SP","Armes"),
                 ("Fusil (RP)",6000,"Arme longue - usage RP avec SP","Armes"),
                 ("Gilet pare-balles",1500,"Protection RP","Équipement"),
                 ("Crochets",400,"Outil d'effraction RP","Outils"),
                 ("Talkie crypté",800,"Comms hors Zello (RP)","Outils")])
    @contextmanager
    def tx(self):
        c=self.c.cursor()
        try: yield c; self.c.commit()
        finally: c.close()
    # sp
    def add_sp(self,a,j,s,ss,l,p):
        with self.tx() as c: c.execute("INSERT INTO sp_logs(ts,author_id,joueur,info_sp,info_supp,lieu,part) VALUES(?,?,?,?,?,?,?)",(time.time(),a,j,s,ss,l,p))
    # gangs
    def mk_gang(self,n,ch,d=""):
        with self.tx() as c:
            c.execute("INSERT INTO gangs(nom,chef_id,fond,descr) VALUES(?,?,?,?)",(n,ch,time.time(),d)); g=c.lastrowid
            c.execute("INSERT INTO gmem VALUES(?,?,?,?)",(g,ch,"Chef",time.time())); return g
    def gang_of(self,u):
        with self.tx() as c: c.execute("SELECT g.* FROM gangs g JOIN gmem m ON g.id=m.gid WHERE m.uid=?",(u,)); return c.fetchone()
    def gmems(self,g):
        with self.tx() as c: c.execute("SELECT * FROM gmem WHERE gid=?",(g,)); return c.fetchall()
    def gmem_add(self,g,u,gr="Recrue"):
        with self.tx() as c: c.execute("INSERT OR REPLACE INTO gmem VALUES(?,?,?,?)",(g,u,gr,time.time()))
    def gmem_kick(self,g,u):
        with self.tx() as c: c.execute("DELETE FROM gmem WHERE gid=? AND uid=?",(g,u))
    def gmem_grade(self,g,u,gr):
        with self.tx() as c: c.execute("UPDATE gmem SET grade=? WHERE gid=? AND uid=?",(gr,g,u))
    # primes
    def add_prime(self,t,a,r,p):
        with self.tx() as c: c.execute("INSERT INTO primes(tid,amt,reason,pid,ts) VALUES(?,?,?,?,?)",(t,a,r,p,time.time()))
    def primes(self,t=None):
        with self.tx() as c:
            c.execute("SELECT * FROM primes WHERE active=1"+(" AND tid=?" if t else ""),(t,) if t else ()); return c.fetchall()
    # marché noir / wallet
    def mn_items(self):
        with self.tx() as c: c.execute("SELECT * FROM mn"); return c.fetchall()
    def mn_item(self,i):
        with self.tx() as c: c.execute("SELECT * FROM mn WHERE id=?",(i,)); return c.fetchone()
    def bal(self,u):
        with self.tx() as c:
            r=c.execute("SELECT cash FROM wallet WHERE uid=?",(u,)).fetchone(); return r["cash"] if r else 0
    def set_bal(self,u,v):
        with self.tx() as c: c.execute("INSERT INTO wallet VALUES(?,?) ON CONFLICT(uid) DO UPDATE SET cash=excluded.cash",(u,v))
    def buy(self,u,i,q=1):
        with self.tx() as c: c.execute("INSERT INTO inv VALUES(?,?,?) ON CONFLICT(uid,iid) DO UPDATE SET qte=qte+excluded.qte",(u,i,q))
    def inv(self,u):
        with self.tx() as c: c.execute("SELECT i.qte,m.nom FROM inv i JOIN mn m ON i.iid=m.id WHERE i.uid=?",(u,)); return c.fetchall()
    # candidatures
    def add_cand(self,u,t):
        with self.tx() as c: c.execute("INSERT INTO cand(uid,type,ts) VALUES(?,?,?)",(u,t,time.time())); return c.lastrowid
    def cands(self,s=None):
        with self.tx() as c:
            c.execute("SELECT * FROM cand"+(" WHERE statut=?" if s else ""),(s,) if s else ()); return c.fetchall()
    # tickets
    def add_ticket(self,ch,u,cat):
        with self.tx() as c: c.execute("INSERT INTO tickets(ch,uid,cat) VALUES(?,?,?)",(ch,u,cat)); return c.lastrowid
    def ticket_ch(self,ch):
        with self.tx() as c: c.execute("SELECT * FROM tickets WHERE ch=?",(ch,)); return c.fetchone()
    def close_ticket(self,ch):
        with self.tx() as c: c.execute("UPDATE tickets SET statut='ferme' WHERE ch=?",(ch,))
    # elections
    def mk_elec(self,n,fin):
        with self.tx() as c: c.execute("INSERT INTO elec(nom,statut,fin) VALUES(?,?,?)",(n,"ouverte",fin)); return c.lastrowid
    def add_candi(self,e,u,p):
        with self.tx() as c: c.execute("INSERT INTO candi(eid,uid,parti) VALUES(?,?,?)",(e,u,p))
    def vote(self,e,u):
        with self.tx() as c: c.execute("UPDATE candi SET votes=votes+1 WHERE eid=? AND uid=?",(e,u))
    def open_elec(self):
        with self.tx() as c: c.execute("SELECT * FROM elec WHERE statut='ouverte'"); return c.fetchall()
    def candis(self,e):
        with self.tx() as c: c.execute("SELECT * FROM candi WHERE eid=? ORDER BY votes DESC",(e,)); return c.fetchall()
    # presence / warns
    def set_pres(self,u,d,on):
        with self.tx() as c: c.execute("INSERT INTO pres VALUES(?,?,?,?) ON CONFLICT(uid) DO UPDATE SET dept=excluded.dept,onv=excluded.onv,since=excluded.since",(u,d,int(on),time.time() if on else 0))
    def add_warn(self,u,m,r):
        with self.tx() as c: c.execute("INSERT INTO warns(uid,mid,reason,ts) VALUES(?,?,?,?)",(u,m,r,time.time()))
    def warns(self,u):
        with self.tx() as c: c.execute("SELECT * FROM warns WHERE uid=?",(u,)); return c.fetchall()
db = DB()

# ============================ HELPERS ================================
def D(ts): return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
def eb(t=None,d=None,col=C.GEN,g=None):
    e=discord.Embed(title=t,description=d,color=col)
    if g and g.icon: e.set_thumbnail(url=g.icon.url)
    return e
def ok(d,**k):  return eb("✅ Succès",d,C.OK,**k)
def err(d,**k): return eb("❌ Erreur",d,C.ERR,**k)
def nfo(d,**k): return eb("ℹ️ Information",d,C.INFO,**k)
def _match(m,ids,kw):
    if any(r.id in ids for r in m.roles): return True
    if ids: return False
    return any(any(k.lower() in r.name.lower() for k in kw) for r in m.roles)
def is_staff(m):  return m.guild_permissions.administrator or _match(m,STAFF_IDS,STAFF_KW)
def in_gang(m):   return _match(m,GANG_IDS,GANG_KW)
def staff_ck():
    async def p(i):
        if i.user.id in OWNER_IDS or (i.guild and is_staff(i.user)): return True
        raise app_commands.CheckFailure("Réservé au staff.")
    return app_commands.check(p)
def owner_ck():  return app_commands.check(lambda i: i.user.id in OWNER_IDS)
def gang_ck():
    async def p(i):
        if i.user.id in OWNER_IDS or in_gang(i.user) or db.gang_of(i.user.id): return True
        raise app_commands.CheckFailure("Réservé aux membres d'un gang.")
    return app_commands.check(p)
async def apply_gang_role(m,gang,grade):
    t=None
    for r in m.guild.roles:
        if gang.lower() in r.name.lower() and grade.lower() in r.name.lower(): t=r; break
    if not t:
        for r in m.guild.roles:
            if r.name.lower()==gang.lower(): t=r; break
    if t and t not in m.roles:
        try: await m.add_roles(t,reason=f"gang {gang}")
        except discord.Forbidden: pass

# ============================ VUES ===================================
PANELS={"notif":{"t":"🔔 Notifications","r":["Annonce","Session","Événement","Stream","Spoilers/Nouveauté","Question du jour","Partenariats"]},
        "age":{"t":"🎂 Tranche d'âge","r":["En dessous de 9","9 à 12 ans","13 à 15 ans","16 à 17 ans","18 à 20 ans","21 ans et +"]}}
class RoleSel(discord.ui.Select):
    def __init__(self,k,g):
        opts=[discord.SelectOption(label=n,value=str(discord.utils.get(g.roles,name=n).id)) for n in PANELS[k]["r"] if discord.utils.get(g.roles,name=n)]
        super().__init__(custom_id=f"rolesel:{k}",placeholder=PANELS[k]["t"],min_values=0,max_values=max(1,len(opts)),options=opts or [discord.SelectOption(label="-",value="0")]); self.k=k
    async def callback(self,i):
        want={int(v) for v in self.values if v!="0"}
        allids={discord.utils.get(i.guild.roles,name=n).id for n in PANELS[self.k]["r"] if discord.utils.get(i.guild.roles,name=n)}
        rm=[i.guild.get_role(x) for x in allids if x in {r.id for r in i.user.roles}]
        ad=[i.guild.get_role(x) for x in want if x not in {r.id for r in i.user.roles}]
        try:
            if rm: await i.user.remove_roles(*rm)
            if ad: await i.user.add_roles(*ad)
            await i.response.send_message(embed=ok("Rôles mis à jour."),ephemeral=True)
        except discord.Forbidden:
            await i.response.send_message(embed=err("Le bot doit être AU-DESSUS des rôles du panneau."),ephemeral=True)
class RolesView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None); self._g=None
    def _build(self,g):
        self.clear_items()
        for k in PANELS: self.add_item(RoleSel(k,g))
    async def interaction_check(self,i):
        if not self._g: self._g=i.guild; self._build(i.guild)
        return True
CATS=["Support","Recrutement Staff","Recrutement Job","Partenariat","Plainte / Staff"]
class TicketSel(discord.ui.Select):
    def __init__(self): super().__init__(custom_id="ticketsel",placeholder="Catégorie du ticket",options=[discord.SelectOption(label=c,value=c) for c in CATS])
    async def callback(self,i):
        cat=self.values[0]; g=i.guild; cg=g.get_channel(TICKET_CAT)
        if not cg: return await i.response.send_message(embed=err("TICKET_CAT non configuré dans le fichier."),ephemeral=True)
        ov={g.default_role:discord.PermissionOverwrite(view_channel=False),
            i.user:discord.PermissionOverwrite(view_channel=True,send_messages=True,attach_files=True),
            g.me:discord.PermissionOverwrite(view_channel=True,manage_channels=True)}
        ch=await cg.create_text_channel(f"ticket-{i.user.name}",category=cg,overwrites=ov)
        tid=db.add_ticket(ch.id,i.user.id,cat)
        await ch.send(embed=eb(f"🎫 Ticket #{tid} — {cat}",f"Bonjour {i.user.mention}, décris ta demande. Un staff va s'en occuper.",C.INFO,g),view=CloseView())
        await i.response.send_message(embed=ok(f"Ticket ouvert : {ch.mention}"),ephemeral=True)
class TicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None); self.add_item(TicketSel())
class CloseView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Fermer le ticket",style=discord.ButtonStyle.danger,emoji="🔒",custom_id="ticketclose")
    async def close(self,i,b):
        t=db.ticket_ch(i.channel.id)
        if not is_staff(i.user) and (not t or t["uid"]!=i.user.id):
            return await i.response.send_message(embed=err("Permission refusée."),ephemeral=True)
        db.close_ticket(i.channel.id)
        await i.response.send_message(embed=nfo("Fermeture dans 5s..."))
        await asyncio.sleep(5)
        try: await i.channel.delete()
        except Exception: pass
# --- gangs / marché noir ---
class AddM(discord.ui.Modal,title="Ajouter au gang"):
    who=discord.ui.TextInput(label="ID Discord du membre"); grade=discord.ui.TextInput(label="Grade",required=False,placeholder="Recrue")
    def __init__(s,g): super().__init__(); s.g=g
    async def on_submit(s,i):
        try: u=int(s.who.value)
        except ValueError: return await i.response.send_message(embed=err("ID invalide."),ephemeral=True)
        db.gmem_add(s.g["id"],u,s.grade.value or "Recrue")
        m=i.guild.get_member(u)
        if m: await apply_gang_role(m,s.g["nom"],s.grade.value or "Recrue")
        await i.response.send_message(embed=ok("Membre ajouté."),ephemeral=True)
class KickM(discord.ui.Modal,title="Virer du gang"):
    who=discord.ui.TextInput(label="ID Discord du membre")
    def __init__(s,g): super().__init__(); s.g=g
    async def on_submit(s,i): db.gmem_kick(s.g["id"],int(s.who.value)); await i.response.send_message(embed=ok("Membre retiré."),ephemeral=True)
class GradeM(discord.ui.Modal,title="Changer le grade"):
    who=discord.ui.TextInput(label="ID Discord du membre"); grade=discord.ui.TextInput(label="Nouveau grade")
    def __init__(s,g): super().__init__(); s.g=g
    async def on_submit(s,i): db.gmem_grade(s.g["id"],int(s.who.value),s.grade.value); await i.response.send_message(embed=ok("Grade mis à jour."),ephemeral=True)
class GangView(discord.ui.View):
    def __init__(s,g,m):
        super().__init__(timeout=180); s.g=g
        if g["chef_id"]!=m.id: s.clear_items()
    @discord.ui.button(label="Ajouter",style=discord.ButtonStyle.success,emoji="➕")
    async def a(s,i,b): await i.response.send_modal(AddM(s.g))
    @discord.ui.button(label="Virer",style=discord.ButtonStyle.danger,emoji="🚪")
    async def k(s,i,b): await i.response.send_modal(KickM(s.g))
    @discord.ui.button(label="Grade",style=discord.ButtonStyle.primary,emoji="🎖️")
    async def gr(s,i,b): await i.response.send_modal(GradeM(s.g))
    @discord.ui.button(label="Quitter",style=discord.ButtonStyle.secondary,emoji="👋")
    async def lv(s,i,b):
        if s.g["chef_id"]==i.user.id: return await i.response.send_message(embed=err("Le chef ne peut pas quitter."),ephemeral=True)
        db.gmem_kick(s.g["id"],i.user.id); await i.response.send_message(embed=ok("Tu as quitté le gang."),ephemeral=True)
class MkGang(discord.ui.Modal,title="Créer un gang"):
    nom=discord.ui.TextInput(label="Nom du gang",max_length=32); desc=discord.ui.TextInput(label="Description / territoire",style=discord.TextStyle.paragraph,required=False)
    async def on_submit(s,i):
        if db.gang_of(i.user.id): return await i.response.send_message(embed=err("Déjà dans un gang."),ephemeral=True)
        try: db.mk_gang(s.nom.value,i.user.id,s.desc.value)
        except Exception: return await i.response.send_message(embed=err("Nom déjà pris."),ephemeral=True)
        await apply_gang_role(i.user,s.nom.value,"Chef")
        await i.response.send_message(embed=ok(f"Gang **{s.nom.value}** créé. Utilise `/illégal panel`."))
class MNSel(discord.ui.Select):
    def __init__(s,items):
        super().__init__(placeholder="Acheter un item illégal",options=[discord.SelectOption(label=f"{x['nom']} — {x['prix']}$",value=str(x["id"]),description=(x["descr"] or "")[:80]) for x in items][:25])
    async def callback(s,i):
        it=db.mn_item(int(s.values[0])); w=db.bal(i.user.id)
        if w<it["prix"]: return await i.response.send_message(embed=err(f"Fonds insuffisants : {w}$ / {it['prix']}$."),ephemeral=True)
        db.set_bal(i.user.id,w-it["prix"]); db.buy(i.user.id,it["id"])
        ch=i.guild.get_channel(MN_LOG_CH)
        if ch: await ch.send(embed=eb("🛒 Achat marché noir",f"{i.user.mention} → **{it['nom']}** ({it['prix']}$)",C.ILL,i.guild))
        await i.response.send_message(embed=ok(f"Achat confirmé : **{it['nom']}**\n💰 Reste **{w-it['prix']}$**\n⚠️ Item RP uniquement."),ephemeral=True)
class MNView(discord.ui.View):
    def __init__(s,items): super().__init__(timeout=180); s.add_item(MNSel(items))
    @discord.ui.button(label="Inventaire",style=discord.ButtonStyle.secondary,emoji="🎒")
    async def inv(s,i,b):
        r=db.inv(i.user.id)
        await i.response.send_message(embed=(eb("🎒 Inventaire","\n".join(f"• {x['nom']} x{x['qte']}" for x in r),C.ILL,i.guild) if r else nfo("Vide.")),ephemeral=True)
    @discord.ui.button(label="Solde",style=discord.ButtonStyle.primary,emoji="💰")
    async def bal(s,i,b): await i.response.send_message(embed=nfo(f"Solde illégal : **{db.bal(i.user.id)}$**"),ephemeral=True)
class RecrM(discord.ui.Modal):
    def __init__(s,t): super().__init__(title=f"Candidature — {t}"); s.t=t
    mot=discord.ui.TextInput(label="Motivation & expérience RP",style=discord.TextStyle.paragraph,max_length=1000)
    disp=discord.ui.TextInput(label="Disponibilités",max_length=200)
    async def on_submit(s,i):
        cid=db.add_cand(i.user.id,s.t)
        e=eb(f"📝 Candidature #{cid} — {s.t}",guild=i.guild); e.add_field(name="Candidat",value=i.user.mention)
        e.add_field(name="Motivation",value=s.mot.value[:1000],inline=False); e.add_field(name="Dispo",value=s.disp.value)
        ch=i.guild.get_channel(CH_RECRUT_STAFF) if s.t=="Staff" else None
        if ch: await ch.send(embed=e)
        await i.response.send_message(embed=ok(f"Candidature #{cid} envoyée. Délai 1-7 jours."),ephemeral=True)

# ============================ GROUPES ================================
illegal_grp = app_commands.Group(name="illégal", description="Commandes illégales / gangs")
panel_grp   = app_commands.Group(name="panel",  description="Panneaux RP")

# ============================ BOT ====================================
intents=discord.Intents.default(); intents.members=True; intents.message_content=True
class Bot(commands.Bot):
    def __init__(s):
        super().__init__(command_prefix="!",intents=intents,activity=discord.Activity(type=discord.ActivityType.watching,name=f"ERLC • {JOIN_CODE}"))
        s.db=db
    async def setup_hook(s):
        s.add_view(RolesView()); s.add_view(TicketView()); s.add_view(CloseView())
        s.tree.add_command(illegal_grp); s.tree.add_command(panel_grp)
        g=discord.Object(id=GUILD_ID); s.tree.copy_global_to(guild=g); await s.tree.sync(guild=g)
    async def on_ready(s):
        print(f"\n🚀 {s.user} ({s.user.id})  —  {len(s.guilds)} serveur(s)\n")
        if not getattr(s,"_sync_on",False): s._sync_on=True; asyncio.create_task(s._syncloop())
    async def _syncloop(s):
        await s.wait_until_ready()
        while not s.is_closed():
            await s._write_site(); await asyncio.sleep(SYNC_SEC)
    async def _write_site(s):
        g=s.get_guild(GUILD_ID)
        if not g: return
        on=sum(1 for m in g.members if m.status!=discord.Status.offline)
        tx=sum(1 for c in g.channels if isinstance(c,discord.TextChannel)); vc=sum(1 for c in g.channels if isinstance(c,discord.VoiceChannel))
        data={"updated_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
              "server":{"id":g.id,"name":g.name,"join_code":JOIN_CODE,"description":SERVER_DESC,"created_at":g.created_at.isoformat(),"icon":g.icon.url if g.icon else None},
              "stats":{"members":g.member_count,"online":on,"roles":len(g.roles),"channels":len(g.channels),"text_channels":tx,"voice_channels":vc,"boost_level":g.premium_tier,"boosts":g.premium_subscription_count or 0},
              "team":TEAM,"departments":DEPARTMENTS,"socials":SOCIALS}
        os.makedirs(os.path.dirname(SITE_JSON),exist_ok=True)
        with open(SITE_JSON,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)
    async def on_member_join(s,m):
        if m.guild.id==GUILD_ID: await s._write_site()
    async def on_member_remove(s,m):
        if m.guild.id==GUILD_ID: await s._write_site()
    async def on_app_command_error(s,i,e):
        if isinstance(e,app_commands.CheckFailure): return await i.response.send_message(embed=err(str(e)),ephemeral=True)
        if isinstance(e,app_commands.MissingPermissions): return await i.response.send_message(embed=err("Permissions insuffisantes."),ephemeral=True)
        traceback.print_exception(type(e),e,e.__traceback__)
        try: await i.response.send_message(embed=err("Erreur interne, le dev a été notifié."),ephemeral=True)
        except Exception: pass
bot=Bot()

# ============================ COMMANDES ==============================
@bot.tree.command(name="info",description="Informations sur un membre")
async def info(i:discord.Interaction,membre:discord.Member=None):
    m=membre or i.user; g=db.gang_of(m.id)
    e=eb(f"👤 {m.display_name}",guild=i.guild); e.set_thumbnail(url=m.display_avatar.url)
    e.add_field(name="Pseudo",value=m.mention); e.add_field(name="ID",value=str(m.id))
    e.add_field(name="Arrivé le",value=discord.utils.format_dt(m.joined_at,"D")); e.add_field(name="Rôles",value=str(len(m.roles)-1))
    e.add_field(name="Gang",value=g["nom"] if g else "Aucun"); e.add_field(name="Staff ?",value="Oui" if is_staff(m) else "Non")
    await i.response.send_message(embed=e)

@bot.tree.command(name="stats",description="Statistiques du serveur")
async def stats(i:discord.Interaction):
    g=i.guild; e=eb(f"📊 {g.name}",guild=g)
    e.add_field(name="Membres",value=str(g.member_count)); e.add_field(name="En ligne",value=str(sum(1 for m in g.members if m.status!=discord.Status.offline)))
    e.add_field(name="Rôles",value=str(len(g.roles))); e.add_field(name="Salons",value=str(len(g.channels)))
    e.add_field(name="Code de jeu",value=f"`{JOIN_CODE}`"); e.add_field(name="Créé le",value=discord.utils.format_dt(g.created_at,"D"))
    await i.response.send_message(embed=e)

@bot.tree.command(name="aide",description="Liste des commandes")
async def aide(i:discord.Interaction):
    e=eb("📖 Commandes de Sherbrooke RP",guild=i.guild)
    e.add_field(name="🌐 Général",value="`/info` `/stats` `/aide` `/verify`")
    e.add_field(name="🎭 Rôles & Tickets",value="`/setup_panneaux` (staff)")
    e.add_field(name="📝 Recrutement",value="`/candidature` `/candidatures_liste`")
    e.add_field(name="🚨 SP",value="`/splog` (staff)")
    e.add_field(name="🩸 Illégal",value="`/illégal panel` `/illégal creer` `/illégal cash` `/panel marché-noir` `/prime` `/primes`")
    e.add_field(name="⚖️ Justice",value="`/poursuite` `/mandat`")
    e.add_field(name="🛡️ Modération",value="`/warn` `/mute` `/kick` `/ban` `/blacklist` `/clear`")
    e.add_field(name="🏢 Départements",value="`/service` `/matricule`"); e.add_field(name="🗳️ Politique",value="`/election`")
    await i.response.send_message(embed=e,ephemeral=True)

@bot.tree.command(name="verify",description="Vérification du compte Roblox")
class _VM(discord.ui.Modal,title="Vérification Roblox"):
    pseudo=discord.ui.TextInput(label="Pseudo Roblox exact",max_length=32)
    async def on_submit(s,i):
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post("https://users.roblox.com/v1/usernames/users",json={"usernames":[s.pseudo.value],"excludeBannedUsers":True}) as r:
                    d=await r.json()
                    if not d.get("data"): return await i.response.send_message(embed=err("Pseudo Roblox introuvable."),ephemeral=True)
        except Exception: pass
        await i.response.send_message(embed=ok(f"Pseudo **{s.pseudo.value}** noté.\n⚠️ La liaison complète se fait via **Melonly / RoVer** dans le salon de vérification."),ephemeral=True)
async def verify(i:discord.Interaction): await i.response.send_modal(_VM())

@bot.tree.command(name="setup_panneaux",description="[STAFF] Crée les panneaux rôles + ticket")
@staff_ck()
async def setup_panneaux(i:discord.Interaction):
    await i.channel.send(embed=eb("🔔 Notifications & Tranche d'âge","Clique sur les menus pour gérer tes rôles.",C.GEN,i.guild),view=RolesView())
    ch=i.guild.get_channel(CH_TICKET_PANEL) or i.channel
    await ch.send(embed=eb("🎫 Support & Tickets","Besoin d'aide, recrutement, partenariat ? Ouvre un ticket.",C.INFO,i.guild),view=TicketView())
    await i.response.send_message(embed=ok("Panneaux créés."),ephemeral=True)

@bot.tree.command(name="candidature",description="Soumettre une candidature")
async def candidature(i:discord.Interaction,type_:str):
    T=["Staff","Job (département)","Gang","Média / Streamer","Entreprise"]
    if type_ not in T: return await i.response.send_message(embed=err(f"Types : {', '.join(T)}"),ephemeral=True)
    await i.response.send_modal(RecrM(type_))

@bot.tree.command(name="candidatures_liste",description="[STAFF] Candidatures en attente")
@staff_ck()
async def cand_liste(i:discord.Interaction):
    r=db.cands("en_attente")
    if not r: return await i.response.send_message(embed=nfo("Aucune candidature en attente."),ephemeral=True)
    e=eb("📋 Candidatures en attente",guild=i.guild)
    for x in r[:20]: e.add_field(name=f"#{x['id']} — {x['type']}",value=f"<@{x['uid']}> • {discord.utils.format_dt(D(x['ts']),'R')}",inline=False)
    await i.response.send_message(embed=e,ephemeral=True)

# ---------- /splog (image 1) ----------
@bot.tree.command(name="splog",description="Logger une SP (Scène Prio)")
@app_commands.rename(info_sp="info-sp",info_supplementaire="info-supplémentaire")
@staff_ck()
async def splog(i:discord.Interaction,joueur:discord.Member,info_sp:str,info_supplementaire:str,lieu:str=None,participants:str=None):
    db.add_sp(i.user.id,str(joueur),info_sp,info_supplementaire,lieu,participants)
    e=eb("🚨 SP Loggée",guild=i.guild,color=C.POL); e.add_field(name="Concerné",value=joueur.mention); e.add_field(name="Loggé par",value=i.user.mention)
    e.add_field(name="Info SP",value=info_sp,inline=False); e.add_field(name="Info supplémentaire",value=info_supplementaire,inline=False)
    if lieu: e.add_field(name="Lieu",value=lieu)
    if participants: e.add_field(name="Participants",value=participants)
    e.set_footer(text=f"{discord.utils.format_dt(discord.utils.utcnow(),'f')}")
    ch=i.guild.get_channel(SP_LOG_CH)
    if ch: await ch.send(embed=e); await i.response.send_message(embed=ok("SP loggée et envoyée au salon de logs."),ephemeral=True)
    else: await i.response.send_message(embed=e)

# ---------- /illégal panel (image 2) ----------
@illegal_grp.command(name="panel",description="Ouvrir le panel des gangs")
@gang_ck()
async def gang_panel(i:discord.Interaction):
    g=db.gang_of(i.user.id)
    if not g:
        v=discord.ui.View(timeout=180); v.add_item(discord.ui.Button(label="Créer un gang",style=discord.ButtonStyle.success))
        v.children[0].callback=lambda x: x.response.send_modal(MkGang())
        return await i.response.send_message(embed=nfo("Pas encore de gang. Crée-le ou rejoins-en un."),view=v,ephemeral=True)
    mems=db.gmems(g["id"]); e=eb(f"🩸 {g['nom']}",guild=i.guild,color=C.ILL)
    e.add_field(name="Chef",value=f"<@{g['chef_id']}>"); e.add_field(name="Membres",value=str(len(mems))); e.add_field(name="Caisse",value=f"{g['cash']}$")
    e.add_field(name="Fondé le",value=discord.utils.format_dt(D(g["fond"]),"D"))
    if g["descr"]: e.add_field(name="Description",value=g["descr"],inline=False)
    e.add_field(name="Composition",value="\n".join(f"• <@{m['uid']}> — *{m['grade']}*" for m in mems[:15]) or "—",inline=False)
    await i.response.send_message(embed=e,view=GangView(g,i.user),ephemeral=True)

@illegal_grp.command(name="creer",description="Créer ton gang")
async def creer(i:discord.Interaction):
    if db.gang_of(i.user.id): return await i.response.send_message(embed=err("Déjà dans un gang."),ephemeral=True)
    await i.response.send_modal(MkGang())

@illegal_grp.command(name="cash",description="[CHEF/STAFF] Créditer du cash illégal")
async def cash(i:discord.Interaction,membre:discord.Member,montant:int,raison:str="Revenus RP"):
    g=db.gang_of(i.user.id)
    if i.user.id not in OWNER_IDS and not is_staff(i.user) and not (g and g["chef_id"]==i.user.id):
        return await i.response.send_message(embed=err("Réservé chef de gang / staff."),ephemeral=True)
    db.set_bal(membre.id,db.bal(membre.id)+montant)
    await i.response.send_message(embed=ok(f"**{montant}$** crédités à {membre.mention} ({raison})."),ephemeral=True)

# ---------- /panel marché-noir (image 2) ----------
@panel_grp.command(name="marché-noir",description="Faire apparaître le menu du marché noir")
@gang_ck()
async def marche_noir(i:discord.Interaction):
    it=db.mn_items()
    if not it: return await i.response.send_message(embed=err("Marché noir vide."),ephemeral=True)
    e=eb("🕶️ Marché Noir","Sélectionne un item. Transactions RP uniquement.",C.ILL,i.guild); e.add_field(name="💰 Ton solde",value=f"{db.bal(i.user.id)}$")
    for x in it[:10]: e.add_field(name=f"{x['nom']} — {x['prix']}$",value=x["descr"] or "—",inline=False)
    await i.response.send_message(embed=e,view=MNView(it),ephemeral=True)

# ---------- /prime (image 2) ----------
@bot.tree.command(name="prime",description="Mettre une prime sur quelqu'un")
@gang_ck()
async def prime(i:discord.Interaction,cible:discord.Member,montant:int,raison:str):
    if montant<=0: return await i.response.send_message(embed=err("Montant invalide."),ephemeral=True)
    w=db.bal(i.user.id)
    if w<montant: return await i.response.send_message(embed=err(f"Fonds insuffisants ({w}$)."),ephemeral=True)
    db.set_bal(i.user.id,w-montant); db.add_prime(cible.id,montant,raison,i.user.id)
    e=eb("💀 PRIME POSÉE",guild=i.guild,color=C.ILL); e.add_field(name="Cible",value=cible.mention); e.add_field(name="Montant",value=f"{montant}$"); e.add_field(name="Raison",value=raison,inline=False); e.add_field(name="Par",value=i.user.mention)
    ch=i.guild.get_channel(MN_LOG_CH)
    if ch: await ch.send(embed=e)
    await i.response.send_message(embed=ok(f"Prime de **{montant}$** sur {cible.mention}."))

@bot.tree.command(name="primes",description="Voir les primes actives")
async def primes(i:discord.Interaction,cible:discord.Member=None):
    r=db.primes(cible.id if cible else None)
    if not r: return await i.response.send_message(embed=nfo("Aucune prime active."),ephemeral=True)
    e=eb("💀 Primes actives",guild=i.guild,color=C.ILL)
    for x in r[:15]: e.add_field(name=f"<@{x['tid']}> — {x['amt']}$",value=x["reason"],inline=False)
    await i.response.send_message(embed=e)

# ---------- justice ----------
@bot.tree.command(name="poursuite",description="Ouvrir une poursuite judiciaire RP")
@staff_ck()
async def poursuite(i:discord.Interaction,accuse:discord.Member,charges:str):
    e=eb("⚖️ Poursuite judiciaire",guild=i.guild,color=C.JUS); e.add_field(name="Accusé",value=accuse.mention); e.add_field(name="Charges",value=charges,inline=False); e.add_field(name="Plaintif / Staff",value=i.user.mention)
    await i.response.send_message(embed=e)
@bot.tree.command(name="mandat",description="Émettre un mandat RP")
@staff_ck()
async def mandat(i:discord.Interaction,cible:discord.Member,type_:str,motif:str):
    e=eb(f"📜 Mandat de {type_}",guild=i.guild,color=C.JUS); e.add_field(name="Cible",value=cible.mention); e.add_field(name="Type",value=type_); e.add_field(name="Motif",value=motif,inline=False); e.add_field(name="Émis par",value=i.user.mention)
    await i.response.send_message(embed=e)

# ---------- modération ----------
async def _mlog(g,e):
    ch=g.get_channel(MOD_LOG_CH)
    if ch: await ch.send(embed=e)
@bot.tree.command(name="warn",description="Avertir un membre")
@staff_ck()
async def warn(i:discord.Interaction,membre:discord.Member,raison:str):
    db.add_warn(membre.id,i.user.id,raison); n=len(db.warns(membre.id))
    e=eb("⚠️ Avertissement",f"{membre.mention} averti ({n} au total).\nRaison : {raison}",C.ERR,i.guild)
    await i.response.send_message(embed=e); await _mlog(i.guild,e)
@bot.tree.command(name="mute",description="Mute temporel")
@staff_ck() @app_commands.checks.bot_has_permissions(moderate_members=True)
async def mute(i:discord.Interaction,membre:discord.Member,minutes:int,raison:str="-"):
    await membre.timeout(dt.timedelta(minutes=minutes),reason=raison)
    e=eb("🔇 Mute",f"{membre.mention} mute {minutes} min. Raison : {raison}",C.ERR,i.guild); await i.response.send_message(embed=e); await _mlog(i.guild,e)
@bot.tree.command(name="kick",description="Expulser un membre")
@staff_ck() @app_commands.checks.bot_has_permissions(kick_members=True)
async def kick(i:discord.Interaction,membre:discord.Member,raison:str="-"):
    e=eb("👢 Kick",f"{membre.mention} expulsé. Raison : {raison}",C.ERR,i.guild); await i.response.send_message(embed=e); await _mlog(i.guild,e); await membre.kick(reason=raison)
@bot.tree.command(name="ban",description="Bannir un membre")
@staff_ck() @app_commands.checks.bot_has_permissions(ban_members=True)
async def ban(i:discord.Interaction,membre:discord.Member,raison:str="-"):
    e=eb("🔨 Ban",f"{membre.mention} banni. Raison : {raison}",C.ERR,i.guild); await i.response.send_message(embed=e); await _mlog(i.guild,e); await membre.ban(reason=raison,delete_message_days=0)
@bot.tree.command(name="blacklist",description="[OWNER] Blacklist serveur")
@owner_ck()
async def blacklist(i:discord.Interaction,membre:discord.Member,raison:str):
    e=eb("⛔ BLACKLIST",f"{membre.mention} blacklisté.\nRaison : {raison}",C.ERR,i.guild); await i.response.send_message(embed=e); await _mlog(i.guild,e)
    try: await membre.ban(reason=f"BLACKLIST - {raison}")
    except Exception: pass
@bot.tree.command(name="clear",description="Supprimer des messages")
@staff_ck() @app_commands.checks.bot_has_permissions(manage_messages=True)
async def clear(i:discord.Interaction,quantite:int):
    await i.channel.purge(limit=quantite); await i.response.send_message(embed=ok(f"{quantite} messages supprimés."),ephemeral=True)

# ---------- départements ----------
DEPTS=["SQ","SPS","SPCIS","Ambulance","MTQ","CGA","Justice"]
@bot.tree.command(name="service",description="En / hors service dans un département")
async def service(i:discord.Interaction,departement:str,en_service:bool):
    if departement not in DEPTS: return await i.response.send_message(embed=err(f"Départements : {', '.join(DEPTS)}"),ephemeral=True)
    db.set_pres(i.user.id,departement,en_service)
    await i.response.send_message(embed=eb(f"{'🟢 EN SERVICE' if en_service else '⚫ HORS SERVICE'} — {departement}",f"{i.user.mention} est **{'en service' if en_service else 'hors service'}**.",C.POL,i.guild))
@bot.tree.command(name="matricule",description="Définir / voir ton matricule RP")
async def matricule(i:discord.Interaction,matricule:str=None):
    if matricule:
        try: await i.user.edit(nick=f"{matricule} | {i.user.display_name.split('|')[-1].strip()}"); await i.response.send_message(embed=ok(f"Matricule : **{matricule}**"),ephemeral=True)
        except discord.Forbidden: await i.response.send_message(embed=err("Le bot ne peut pas changer ton pseudo (rôle trop bas)."),ephemeral=True)
    else: await i.response.send_message(embed=nfo(f"Pseudo actuel : **{i.user.display_name}**"),ephemeral=True)

# ---------- élections ----------
@bot.tree.command(name="election",description="Gérer les élections municipales")
@app_commands.choices(action=[app_commands.Choice(name=n,value=n) for n in ["creer","candidat","voter","resultats"]])
async def election(i:discord.Interaction,action:str,nom:str=None,parti:str=None,candidat:discord.Member=None):
    if action=="creer":
        if not is_staff(i.user): return await i.response.send_message(embed=err("Réservé staff."),ephemeral=True)
        eid=db.mk_elec(nom or "Élection municipale",time.time()+7*86400); return await i.response.send_message(embed=ok(f"Élection #{eid} créée (7 jours)."))
    if action=="candidat":
        oe=db.open_elec()
        if not oe: return await i.response.send_message(embed=err("Aucune élection ouverte."),ephemeral=True)
        db.add_candi(oe[0]["id"],i.user.id,parti or "Indépendant"); return await i.response.send_message(embed=ok("Candidature enregistrée."))
    if action=="voter":
        if not candidat: return await i.response.send_message(embed=err("Indique le candidat."),ephemeral=True)
        oe=db.open_elec()
        if not oe: return await i.response.send_message(embed=err("Aucune élection ouverte."),ephemeral=True)
        db.vote(oe[0]["id"],candidat.id); return await i.response.send_message(embed=ok(f"Vote pour {candidat.mention}."),ephemeral=True)
    if action=="resultats":
        oe=db.open_elec()
        if not oe: return await i.response.send_message(embed=err("Aucune élection ouverte."),ephemeral=True)
        e=eb(f"🗳️ Résultats — {oe[0]['nom']}",guild=i.guild)
        for r in db.candis(oe[0]["id"]): e.add_field(name=f"<@{r['uid']}> ({r['parti']})",value=f"{r['votes']} voix",inline=False)
        await i.response.send_message(embed=e)

# ============================ LANCEMENT ==============================
bot.run(TOKEN)

import os

# =========================
#  CARPETA PERSISTENTE
# %APPDATA%\CFLLauncher\ — nunca se borra
# =========================
APP_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "CFLLauncher")
os.makedirs(APP_DIR, exist_ok=True)

# =========================
#  URLs DE DRIVE
# =========================
# =========================
#  REDES / ENLACES (barra lateral)
#  👉 Rellena estos con tus enlaces reales. Si quedan vacíos, el botón
#     se deshabilita solo (no queda "muerto").
# =========================
GITHUB_URL  = "https://github.com/AlejandroMtzR/LauncherCFL"
DISCORD_URL = ""   # p. ej. "https://discord.gg/tuInvite"
WEB_URL     = ""   # p. ej. "https://chafaland.example.com"

VERSION_URL      = "https://drive.google.com/uc?export=download&id=1oXrV3xaCtD106nNH7iVujnVDPRZfCIEU"
MODPACK_FULL_LINK_URL = "https://drive.google.com/uc?export=download&id=13KFXY61-Fqm_HoSL6vyb110Y7pGyuS6-"
MODPACK_UPDATE_LINK_URL = "https://drive.google.com/uc?export=download&id=1o-E25jsyXs8JEEEImY7uac-lxFfJuBil"
# =========================
#  ARCHIVOS LOCALES
# Todos en %APPDATA%\CFLLauncher\
# =========================
VERSION_FILE   = os.path.join(APP_DIR, "version_local.txt")
PACK_FILE      = os.path.join(APP_DIR, "pack_mods.txt")
INSTALLED_FILE = os.path.join(APP_DIR, "installed.flag")

# ZIP en %TEMP% — no necesita ser permanente
ZIP_NAME = os.path.join(os.getenv("TEMP", APP_DIR), "modpack.zip")


# =========================
# GALERÍA DE IMÁGENES (Drive)
# =========================
#   "https://drive.google.com/file/d/1AbC...XyZ/view?usp=sharing"
#   "https://drive.google.com/uc?export=download&id=1AbC...XyZ"
#   "1AbC...XyZ"            (solo el ID)
GALLERY_IMAGES = [
    "https://drive.google.com/file/d/1sn3zvZvq1HauixuRGVctD4Q6EHwtjSsT/view",
    "https://drive.google.com/file/d/14MHDRg7RAtMCsmTLFkKZz8AEByFU96zV/view",
    "https://drive.google.com/file/d/1_arXFJJjeesBBihRbPzlBsgp_PM5GW9Q/view",
    "https://drive.google.com/file/d/1_l2n3ElEM9w6zYgyoxKQSW62dvwBQKxk/view",
    "https://drive.google.com/file/d/1QGUOsCwCSr1Irl1LxV9Q0gc7lcucdo8B/view",
    "https://drive.google.com/file/d/1yw8_5HeZQThxS931TjoHI-t6Pt-jWe_2/view",
    "https://drive.google.com/file/d/1ohXQzVz6h2kHwO3gY8o16bnWhSFCeXtP/view",
    "https://drive.google.com/file/d/1JH6Ntg29bdtOe1Hw9XkqkxdSkf4ODqHi/view",
    "https://drive.google.com/file/d/1PYqEUX0qLQfRo65KOLbMtOncASle3AfH/view",
    "https://drive.google.com/file/d/1Q9-8O7RdaHvzGhBA1HMfChnHQmnE_vv-/view",

]

# Carpeta local donde se cachean (descargan una sola vez) las imágenes.
GALLERY_DIR = os.path.join(APP_DIR, "gallery")
os.makedirs(GALLERY_DIR, exist_ok=True)



MODS_CATEGORIES = [
    ("⚔️  RPG y Jefes", [
        "L_Ender's Cataclysm", "Mowzie's Mobs", "Alex's Mobs", "Mutant Monsters",
        "Infernal Mobs", "Progressive Bosses", "Artifacts", "Paraglider",
        "Domestication Innovation", "Enchant With Mob", "Simply Tools",
        "More Bows and Arrows", "Advanced Netherite",
    ]),
    ("🌍  Exploración", [
        "Alex's Caves", "Twilight Forest", "Blue Skies", "The Undergarden",
        "Ad Astra", "Deeper and Darker", "The Graveyard", "Tropicraft",
        "Nature Arise", "Dungeons Arise", "Dungeon Crawl", "Awesome Dungeons",
        "Repurposed Structures", "Structory", "Biomes O' Plenty",
        "Regions Unexplored", "Tectonic", "YUNG's Better Dungeons",
        "YUNG's Better Strongholds", "YUNG's Better Mineshafts",
        "YUNG's Better Nether Fortresses", "YUNG's Better Ocean Monuments",
    ]),
    ("❄️  Supervivencia", [
        "Cold Sweat", "Thirst Was Taken", "Serene Seasons", "Comforts",
        "Aquaculture 2", "Farmer's Delight", "Croptopia", "Sleeping Bags",
        "Torchmaster", "Tombstone", "Traveler's Backpack", "Useful Backpacks",
    ]),
    ("🚂  Tecnología", [
        "Create", "Create Addition", "Create New Age", "Steam 'n' Rails",
        "Mekanism", "Mekanism Generators", "Applied Energistics 2",
        "Refined Storage", "Immersive Engineering", "LaserIO", "Iron Furnaces",
        "Iron Chests", "Building Gadgets 2", "Automobility", "Immersive Aircraft",
    ]),
    ("🏠  Construcción y Decoración", [
        "MrCrayfish's Furniture Mod", "Refurbished Furniture", "Handcrafted",
        "Adorn", "Chisels & Bits", "Fairy Lights", "Macaw's Furniture",
        "Macaw's Doors", "Macaw's Roofs", "Macaw's Windows", "Supplementaries",
        "Decorative Blocks", "Additional Lights", "Connected Glass",
        "Dustrial Decor",
    ]),
]
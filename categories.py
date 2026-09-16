"""Groups of the .par: the 609 lists sorted into a dozen categories a modder
thinks in. Sheet -> category; the Units sheet is split by the name of the
list's first entry (NPC-ish prefixes vs. everything else = enemies).

One place for the table: the tree, the dropdown and the guide's reference
chapter all read it, so they never drift apart.
"""

CATEGORIES = [
    'Player', 'NPCs', 'Enemies', 'Animals & Mounts', 'Weapons & Missiles',
    'Armour & Equipment', 'Magic & Effects', 'Potions & Items',
    'Objects & Buildings', 'Traps', 'Sounds & Voices', 'Meshes & Animations',
    'Game Parameters', 'Other',
]

SHEET_CATEGORY = {
    'Heroes': 'Player', 'HeroTalks': 'Player',
    'ShopUnits': 'NPCs', 'UnitTalks': 'NPCs',
    'BasicUnits': 'Animals & Mounts',
    'Weapon': 'Weapons & Missiles', 'MagicClub': 'Weapons & Missiles',
    'Missiles': 'Weapons & Missiles', 'PierceMissileSlots': 'Weapons & Missiles',
    'Equipment': 'Armour & Equipment', 'EquipmentArtefacts': 'Armour & Equipment',
    'MagicCard': 'Magic & Effects', 'Dynamics': 'Magic & Effects',
    'PotionArtefacts': 'Potions & Items', 'AlchemyFormulaArtefacts': 'Potions & Items',
    'SpecialArtefacts': 'Potions & Items', 'CustomArtefacts': 'Potions & Items',
    'Passives': 'Objects & Buildings', 'SimplePassives': 'Objects & Buildings',
    'Containers': 'Objects & Buildings', 'Gates': 'Objects & Buildings',
    'Teleports': 'Objects & Buildings', 'Markers': 'Objects & Buildings',
    'Traps': 'Traps',
    'SoundPack': 'Sounds & Voices', 'SoundPacksSet': 'Sounds & Voices',
    'UnitMeshes': 'Meshes & Animations', 'BasicUnitsAnimations': 'Meshes & Animations',
    'UnitsAnimations': 'Meshes & Animations', 'UnitsAnimationsFiles': 'Meshes & Animations',
    'CustomScalers': 'Meshes & Animations', 'MeshButtonViewParams': 'Meshes & Animations',
    'CameraTracks': 'Meshes & Animations',
    'CommonGameParams': 'Game Parameters', 'ObjectParticles': 'Game Parameters',
    'InventoryDialogParams': 'Game Parameters', 'SpecialUpdatesLinks': 'Game Parameters',
}

# Units lists whose first entry starts like this are people you talk to.
# Measured on the 95 Units lists of the Update16 par (16.09.2026): the
# NPC lists start with CITIZEN_*, BARTENDER, CHAR_, KARGA, GIRIZA, SKELDEN,
# SOLDIER_*, WARRIOR, MASTER_AIR, SOUL_DEFENDER, SISTER, NPC_Q_* and
# THE_1_COACH; everything else (MO_*, GOBLIN, ORC, SKELETON, G_* ...) fights.
NPC_PREFIXES = ('CITIZEN', 'BARTENDER', 'CHAR_', 'KARGA', 'GIRIZA', 'SKELDEN',
                'SOLDIER', 'WARRIOR', 'MASTER_', 'SOUL_', 'SISTER', 'NPC_',
                'THE_1_COACH', 'SHOP', 'TRADER', 'GUARD', 'PRIEST', 'MERCHANT')

SOURCE = 'categories.py; sheets from TwoWorlds.xls (SDK), counts measured on WDFiles\\Update16.wd, 16.09.2026'


def category_of(sheet, first_name):
    if sheet == 'Units':
        up = (first_name or '').upper()
        return 'NPCs' if up.startswith(NPC_PREFIXES) else 'Enemies'
    return SHEET_CATEGORY.get(sheet, 'Other')


def sheets_of(category):
    """Sheets that feed a category (Units appears under NPCs and Enemies)."""
    out = [s for s, c in SHEET_CATEGORY.items() if c == category]
    if category in ('NPCs', 'Enemies'):
        out.insert(0, 'Units')
    return out

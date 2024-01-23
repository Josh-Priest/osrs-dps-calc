"""
    Script to generate a monsters.json of all the monsters on the OSRS Wiki, and downloads images for each of them.
    The JSON file is placed in ../src/lib/monsters.json

    The images are placed in ../cdn/monsters/. This directory is NOT included in the Next.js app bundle, and should
    be deployed separately to our file storage solution.

    Written for Python 3.9.
"""
import os.path

import requests
import json
import urllib.parse
import re

FILE_NAME = '../cdn/json/monsters.json'
WIKI_BASE = 'https://oldschool.runescape.wiki'
API_BASE = WIKI_BASE + '/api.php'
IMG_PATH = '../cdn/monsters/'

REQUIRED_PRINTOUTS = [
    'Attack bonus',
    'Attack level',
    'Attack speed',
    'Attack style',
    'Combat level',
    'Crush defence bonus',
    'Defence level',
    'Hitpoints',
    'Image',
    'Immune to poison',
    'Immune to venom',
    'Magic Damage bonus',
    'Magic attack bonus',
    'Magic defence bonus',
    'Magic level',
    'Max hit',
    'Monster attribute',
    'Name',
    'Range attack bonus',
    'Ranged Strength bonus',
    'Range defence bonus',
    'Ranged level',
    'Slash defence bonus',
    'Slayer category',
    'Slayer experience',
    'Stab defence bonus',
    'Strength bonus',
    'Strength level',
    'Size',
    'NPC ID',
    'Category'
]


def get_monster_data():
    monsters = {}
    offset = 0
    while True:
        print('Fetching monster info: ' + str(offset))
        query = {
            'action': 'ask',
            'format': 'json',
            'query': '[[Uses infobox::Monster]]|?' + '|?'.join(REQUIRED_PRINTOUTS) + '|limit=500|offset=' + str(offset)
        }
        r = requests.get(API_BASE + '?' + urllib.parse.urlencode(query), headers={
            'User-Agent': 'osrs-dps-calc (https://github.com/weirdgloop/osrs-dps-calc)'
        })
        data = r.json()

        if 'query' not in data or 'results' not in data['query']:
            # No results?
            break

        monsters = monsters | data['query']['results']

        if 'query-continue-offset' not in data or int(data['query-continue-offset']) < offset:
            # If we are at the end of the results, break out of this loop
            break
        else:
            offset = data['query-continue-offset']
    return monsters


def get_printout_value(prop):
    # SMW printouts are all arrays, so ensure that the array is not empty
    if not prop:
        return None
    else:
        return prop[0]


def has_category(category_array, category):
    return next((c for c in category_array if c['fulltext'] == "Category:%s" % category), None)


def main():
    # Grab the monster info using SMW, including all the relevant printouts
    wiki_data = get_monster_data()

    # Convert the data into our own JSON structure
    data = []
    required_imgs = []

    # Loop over the monsters data from the wiki
    for k, v in wiki_data.items():
        print('Processing ' + k)

        # Sanity check: make sure that this monster has printouts from SMW
        if 'printouts' not in v:
            print(k + ' is missing SMW printouts - skipping.')
            continue

        po = v['printouts']

        # We split the key instead of using the Version anchor prop here to account for monsters with custom |smwname=
        try:
            version = k.split('#', 1)[1]
        except IndexError:
            version = ''

        # If this is a CoX monster Challenge Mode variant, remove it. This will be handled by the calculator UI.
        if 'Challenge Mode' in version:
            print(k + ' is a CoX CM variant - skipping.')
            continue

        # Skip monsters that aren't in the main namespace on the wiki
        if re.match("^([A-z]*):", k):
            continue

        # Skip "monsters" that are actually non-interactive scenery, or don't exist
        if (
            has_category(po['Category'], 'Non-interactive scenery')
            or has_category(po['Category'], 'Discontinued content')
        ):
            continue

        monster = {
            'id': get_printout_value(po['NPC ID']),
            'name': k.rsplit('#', 1)[0] or '',
            'version': version,
            'image': '' if not po['Image'] else po['Image'][0]['fulltext'].replace('File:', ''),
            'level': get_printout_value(po['Combat level']) or 0,
            'speed': get_printout_value(po['Attack speed']) or 0,
            'size': get_printout_value(po['Size']) or 0,
            'skills': [
                get_printout_value(po['Attack level']) or 0,
                get_printout_value(po['Defence level']) or 0,
                get_printout_value(po['Hitpoints']) or 0,
                get_printout_value(po['Magic level']) or 0,
                get_printout_value(po['Ranged level']) or 0,
                get_printout_value(po['Strength level']) or 0
            ],
            'offensive': [
                get_printout_value(po['Attack bonus']) or 0,
                get_printout_value(po['Magic Damage bonus']) or 0,
                get_printout_value(po['Magic attack bonus']) or 0,
                get_printout_value(po['Range attack bonus']) or 0,
                get_printout_value(po['Ranged Strength bonus']) or 0,
                get_printout_value(po['Strength bonus']) or 0
            ],
            'defensive': [
                get_printout_value(po['Crush defence bonus']) or 0,
                get_printout_value(po['Magic defence bonus']) or 0,
                get_printout_value(po['Range defence bonus']) or 0,
                get_printout_value(po['Slash defence bonus']) or 0,
                get_printout_value(po['Stab defence bonus']) or 0
            ],
            'attributes': po['Monster attribute'] or []
        }

        # Prune...
        if (
            # ...monsters that do not have any hitpoints
            monster['skills'][2] == 0
            # ...monsters that don't have an ID
            or monster['id'] is None
            # ...monsters that are historical
            or '(historical)' in str.lower(monster['name'])
            # ...monsters from the PvM arena
            or '(pvm arena)' in str.lower(monster['name'])
            # ...monsters from DMM Apocalypse
            or '(deadman: apocalypse)' in str.lower(monster['name'])
        ):
            continue

        # vard's defence and str change throughout the fight and the ask query doesn't pull that field properly
        if monster['name'] == 'Vardorvis':
            if monster['version'] == 'Post-Quest':
                monster['skills'][1] = 215
                monster['skills'][5] = 270
            elif monster['version'] == 'Awakened':
                monster['skills'][1] = 268
                monster['skills'][5] = 391
            elif monster['version'] == 'Quest':
                monster['skills'][1] = 180
                monster['skills'][5] = 210

        data.append(monster)
        if not monster['image'] == '':
            required_imgs.append(monster['image'])

    print('Total monsters: ' + str(len(data)))

    # Save the JSON
    with open(FILE_NAME, 'w') as f:
        print('Saving to JSON at file: ' + FILE_NAME)
        json.dump(data, f, ensure_ascii=False, indent=2)

    success_img_dls = 0
    failed_img_dls = 0
    skipped_img_dls = 0
    required_imgs = set(required_imgs)

    # Fetch all the images from the wiki and store them for local serving
    for idx, img in enumerate(required_imgs):
        if os.path.isfile(IMG_PATH + img):
            skipped_img_dls += 1
            continue

        print(f'({idx}/{len(required_imgs)}) Fetching image: {img}')
        r = requests.get(WIKI_BASE + '/w/Special:Filepath/' + img, headers={
            'User-Agent': 'osrs-dps-calc (https://github.com/weirdgloop/osrs-dps-calc)'
        })
        if r.status_code == 200:
            with open(IMG_PATH + img, 'wb') as f:
                f.write(r.content)
                print('Saved image: ' + img)
                success_img_dls += 1
        else:
            print('Unable to save image: ' + img)
            failed_img_dls += 1

    print('Total images saved: ' + str(success_img_dls))
    print('Total images skipped (already exists): ' + str(skipped_img_dls))
    print('Total images failed to save: ' + str(failed_img_dls))


main()

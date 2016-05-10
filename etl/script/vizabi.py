# -*- coding: utf-8 -*-
"""update meta.json and en.json with latest data"""


import pandas as pd
import numpy as np
import os
from common import to_concept_id, to_dict_dropna
from collections import OrderedDict


def update_enjson(enj, ddf_concept, graphs):
    """update the existing en.json with new concepts.

    enj: source en.json
    ddf_concept: ddf--concepts of this repo.
    graphs: graph settings file to get the menu levels indicator.
    """
    trs = ddf_concept[['concept', 'name', 'unit', 'description']]
    # remove the country groups and dont-panic-poverty concepts, which
    # will be process differently.
    trs = trs.iloc[6:-3].copy()
    # create indicator name, unit, description of each concepts.
    trs['key_1'] = 'indicator/'+trs['concept']
    trs['key_2'] = 'unit/'+trs['concept']
    trs['key_3'] = 'description/'+trs['concept']

    trs1 = trs.drop('concept', axis=1).set_index('key_1')
    trs2 = trs.drop('concept', axis=1).set_index('key_2')
    trs3 = trs.drop('concept', axis=1).set_index('key_3')

    name = trs1['name'].fillna("")
    unit = trs2['unit'].fillna("")
    desc = trs3['description'].fillna("")

    # check each item in old en.json and name/unit/description series
    # if an item is not in en.json, insert that item
    # if the item is in en.json, update that item if the item in en.json
    # only if the item in en.json is empty.
    for k, v in name.to_dict().items():
        if k not in enj.keys():
            enj.update({k: v})
        else:
            if len(enj[k]) == 0:
                enj.update({k: v})

    for k, v in unit.to_dict().items():
        if k not in enj.keys():
            enj.update({k: v})
        else:
            if len(enj[k]) == 0:
                enj.update({k: v})

    for k, v in desc.to_dict().items():
        if k not in enj.keys():
            enj.update({k: v})
        else:
            if len(enj[k]) == 0:
                enj.update({k: v})

    # menu levels.
    levels = graphs[['concept', 'menu_level1', 'menu_level_2']]

    l1 = levels['menu_level1'].unique()
    l2 = levels['menu_level_2'].unique()

    for i in l1:
        if i is not np.nan:
            key = to_concept_id(i)
            enj['indicator/'+key] = i

    for i in l2:
        if i is not np.nan:
            key = to_concept_id(i)
            enj['indicator/'+key] = i

    # country groupings
    c5 = ddf_concept[ddf_concept['concept_type'] == 'entity_set'].copy()
    for i, v in c5.iterrows():
        enj['indicator/'+'geo.'+v['concept']] = v['name']

    return enj


def generate_metadata(ddf_concept, graphs, meta2, area, outdir, oneset=False):
    """Generate the metadata.json.

    ddf_concept: ddf--concepts for this repo.
    graphs: graph settings
    meta2: the old metadata.json
    area: area_categorizarion.json
    outdir: the output dir of datapoints.
    oneset: if oneset is true, only one entity set(world_4region) will be added.
    """
    # use OrderedDict in order to keep the order of insertion.
    indb = OrderedDict([['indicatorsDB', OrderedDict()]])

    # rename indicator_url to sourceLink
    ddf_concept = ddf_concept.rename(columns={'indicator_url': 'sourceLink'})

    # geo property
    geo_list = ['geo', 'name', 'latitude', 'longitude',
                'world_4region']
    geo_cols = ['scales', 'sourceLink', 'color']

    ddf_concept = ddf_concept.set_index('concept')
    for k in geo_list:
        values = ddf_concept.loc[[k], geo_cols]
        values.columns = ['scales', 'sourceLink', 'color']
        value_dict = to_dict_dropna(values)
        if k == 'geo':
            key = k
        else:
            key = 'geo.'+k
        indb['indicatorsDB'][key] = value_dict[k]
        indb['indicatorsDB'][key]['use'] = 'property'
        # when reading from file, color property becomes string.
        # so we eval it to get the dict back.
        # TODO: using eval() may cause security problem.
        if 'color' in indb['indicatorsDB'][key].keys():
            indb['indicatorsDB'][key]['color'] = eval(indb['indicatorsDB'][key]['color'])

    # manually add a _default and time indicator
    indb['indicatorsDB']['time'] = {
        "use": "indicator",
        "scales": ["time"],
        "sourceLink": ""
    }
    indb['indicatorsDB']['_default'] = {
        "use": "constant",
        "scales": ["ordinal"],
        "sourceLink": ""
    }

    if not oneset:
        group_data = ddf_concept[ddf_concept['domain'] == 'geo'][geo_cols]
        group_names = group_data.index
        group_names = group_names.drop(['country', 'world_4region'])

        for g in sorted(group_names):
            value_dict = to_dict_dropna(group_data.ix[[g]])
            key = 'geo.'+g
            indb['indicatorsDB'][key] = value_dict[g]
            indb['indicatorsDB'][key]['use'] = 'property'
            # TODO: using eval() may cause security problem.
            if 'color' in indb['indicatorsDB'][key].keys():
                indb['indicatorsDB'][key]['color'] = eval(indb['indicatorsDB'][key]['color'])

    ddf_concept = ddf_concept.reset_index()

    # all measure types.
    measure_cols = ['concept', 'sourceLink', 'scales', 'interpolation', 'color']
    mdata = ddf_concept[ddf_concept['concept_type'] == 'measure'][measure_cols]
    mdata = mdata.set_index('concept')
    mdata = mdata.drop(['longitude', 'latitude'])
    mdata.columns = ['sourceLink', 'scales', 'interpolation', 'color']
    mdata['use'] = 'indicator'

    mdata_dict = to_dict_dropna(mdata)
    for k in sorted(mdata_dict.keys()):
        indb['indicatorsDB'][k] = mdata_dict.get(k)

    for i in indb['indicatorsDB'].keys():
        fname = os.path.join(outdir, 'ddf--datapoints--'+i+'--by--geo--time.csv')
        try:
            df = pd.read_csv(fname, dtype={i: float, 'time': int})
        except (OSError, IOError):
            print('no datapoints for ', i)
            continue

        # domain and availability
        dm = [float(df[i].min()), float(df[i].max())]
        av = [int(df['time'].min()), int(df['time'].max())]

        # domain_quantiles_10_90:
        # 1) sort by indicator value
        # 2) remove top and bottom 10% of values (os if 100 points, remove 10 from top and bottom)
        # 3) take first and last value of what's left as min and max in the property above.
        values_sorted = df[i].sort_values().values
        q_10 = np.round(len(values_sorted) / 10)
        q_90 = -1 * q_10 - 1

        q_05 = np.round(len(values_sorted) / 20)
        q_95 = -1 * q_05 - 1

        # values_sorted = values_sorted[q_10:q_90]
        # domain_quantiles_10_90 = [values_sorted.min(), values_sorted.max()]

        domain_quantiles_10_90 = [values_sorted[q_10], values_sorted[q_90]]
        domain_quantiles_05_95 = [values_sorted[q_05], values_sorted[q_95]]

        indb['indicatorsDB'][i].update({
            'domain': dm, 'availability': av,
            'domain_quantiles_10_90': domain_quantiles_10_90,
            'domain_quantiles_05_95': domain_quantiles_05_95
        })

    # newdb = OrderedDict([[key, indb['indicatorsDB'][key]] for key in sorted(indb['indicatorsDB'].keys())])
    # indb['indicatorsDB'] = newdb

    # indicator Trees
    indb['indicatorsTree'] = OrderedDict([['id', '_root'], ['children', []]])
    ti = OrderedDict([['id', 'time']])
    pro = OrderedDict([['id', '_properties'], ['children', [{'id': 'geo'}, {'id': 'geo.name'}]]])

    indb['indicatorsTree']['children'].append(ti)
    all_levels = graphs[['concept', 'menu_level1', 'menu_level_2']].sort_values(['menu_level1', 'menu_level_2'], na_position='first')

    # change nans to something more convenient
    all_levels['menu_level1'] = all_levels['menu_level1'].apply(to_concept_id).fillna('0')
    all_levels['menu_level_2'] = all_levels['menu_level_2'].apply(to_concept_id).fillna('1')

    all_levels = all_levels.set_index('concept')

    g = all_levels.groupby('menu_level1').groups

    ks = list(sorted(g.keys()))

    # move 'for_advanced_user' to the end of list.
    if 'for_advanced_users' in ks:
        ks.remove('for_advanced_users')
        ks.append('for_advanced_users')

    # loop though all level1 keys, for each key:
    # if key is nan, insert to the _root tree with {'id': concept_name}
    # else, insert {'id': concept_name, 'children': []}
    # then group all concepts with the key as level 1 menu by level 2 menu
    # loop though each level 2 group and do the same insertion logic as above.
    for key in ks:
        if key == '0':  # so it's NaN
            for i in sorted(g[key]):
                indb['indicatorsTree']['children'].append({'id': i})
            # insert _properities entity after the root level menus as requested.
            indb['indicatorsTree']['children'].append(pro)
            if not oneset:
                for i in range(len(area)):
                    key = 'geo.'+to_concept_id(area[i]['n'])
                    # remove geo.geographic_regions_in_4_colors as requested
                    # by Jasper
                    if key == 'geo.geographic_regions_in_4_colors':
                        continue
                    indb['indicatorsTree']['children'][-1]['children'].append({'id': key})
            indb['indicatorsTree']['children'][-1]['children'].append({'id': 'geo.world_4region'})
            continue

        od = OrderedDict([['id', key], ['children', []]])
        indb['indicatorsTree']['children'].append(od)

        g2 = all_levels.ix[g[key]].groupby('menu_level_2').groups
        for key2 in sorted(g2.keys()):
            if key2 == '1':  # it's NaN
                for i in sorted(g2[key2]):
                    indb['indicatorsTree']['children'][-1]['children'].append({'id': i})
            else:
                od = OrderedDict([['id', key2], ['children', []]])
                indb['indicatorsTree']['children'][-1]['children'].append(od)
                for i in sorted(g2[key2]):
                    indb['indicatorsTree']['children'][-1]['children'][-1]['children'].append({'id': i})

    return indb

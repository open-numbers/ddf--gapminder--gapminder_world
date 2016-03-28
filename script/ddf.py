# -*- coding: utf-8 -*-
"""create ddf files for gapminder world data, from the origin
json version files.
"""

import pandas as pd
import numpy as np
import os
from common import to_concept_id


# helper functions
def rename_col(s, idt, concepts):
    '''map concept name to concept id.

    idt: DataFrame containing concept name and hashed file name.
    concepts: DataFrame containing concept name and concept id.
    '''
    real = idt[idt['-t-ind'] == s]['-t-name'].iloc[0]
    try:
        cid = concepts[concepts['full_name'] == real]['concept'].iloc[0]
    except:
        print('concept not found: ', real)
        raise
    return cid


def rename_geo(s, gwidmap, isomap):
    """map gwid to iso code as used in systema_globalis repo.

    gwidmap: DataFrame containing gwid and iso digit codes
    isomap: DataFrame containing the old and new iso codes for each country
    """
    iso = gwidmap.ix[s]['ISO3dig_ext']
    return isomap.ix[iso].values


# Entities of country gourps
def extract_entities_groups(regs, gps):
    """extract all country groups entities

    regs: regions.json, contains country/region name and gwid.
    gps: area_categorizarion.json, contains groups name and group levels
    """
    res = {}

    regd = {}  # a dictionary, which keys are region id and values are region names
    for i in regs:
        regd[i.get(list(i.keys())[0])] = list(i.keys())[0]

    for i, n in gps.n.apply(to_concept_id).iteritems():
        df = pd.DataFrame([], columns=[n, 'name', 'gwid', 'is--'+n])
        df['gwid'] = gps.iloc[i]['groupings'].keys()
        if i == 4:
            df[n] = df['gwid'].apply(lambda x: to_concept_id(regd[x], sub='[/ -\.\*";\[\]]+', sep=''))
        else:
            df[n] = df['gwid'].apply(lambda x: to_concept_id(regd[x], sub='[/ -\.\*";\[\]]+'))

            df['name'] = df['gwid'].apply(lambda x: regd[x])
        df['is--'+n] = 'TRUE'
        res[n] = df
    return res


# Entities of Country
def extract_entities_country(regs, geo, gps, geo_sg, geo_map=False):
    """if geo_map is True, return a geomap which maps the old country id to new id
    else return the country entities with new id.

    regs: regions.json, contains country/region name and gwid.
    geo: country_synonyms.xlsx, contains all country info
    gps: area_categorizarion.json, contains groups name and group levels
    geo_sg: country entities from systema_globalis
    """
    regd = {}
    for i in regs:
        regd[i.get(list(i.keys())[0])] = list(i.keys())[0]

    geo_ = geo[['ISO3dig_ext', 'Gwid']]
    geo_ = geo_.set_index('Gwid')
    geo_2 = geo.set_index('Gwid').drop('ISO3dig_ext', axis=1)

    country = geo_.copy()

    # loop though all groupings, build a dataframe which gwid is the index and
    # group names are columns.
    for i, n in gps.n.apply(to_concept_id).iteritems():
        res = {}

        for k, v in gps.iloc[i]['groupings'].items():
            for gwid in v:
                if gwid:
                    res[gwid] = to_concept_id(regd[k], sub='[/ -\.\*";\[\]]+')

        ser = pd.Series(res)

        country[n] = ser

    # combine the groupings info and other info, and do some cleanups.
    country2 = pd.concat([country, geo_2], axis=1)
    country2 = country2.reset_index()
    country2 = country2.rename(columns={'NAME': 'Upper Case Name', 'Use Name': 'Name', 'ISO3dig_ext': 'country_2'})
    country2.columns = list(map(to_concept_id, country2.columns))
    country2['is--country'] = 'TRUE'

    # adding world_4region data
    country3 = geo_sg[['geo', 'world_4region', 'latitude', 'longitude', 'name']]
    country3 = country3.rename(columns={'geo': 'country'}).set_index('name')

    # the final dataframe
    country4 = pd.concat([country2.set_index('name'), country3], axis=1)
    country4 = country4.reset_index()
    country4 = country4.rename(columns={'index': 'name'})

    if not geo_map:
        country4 = country4.drop('country_2', axis=1)
        cols = country4.columns.drop(['country', 'gwid', 'name'])
        ex_col = np.r_[['country', 'gwid', 'name'], cols]
        return country4.loc[:, ex_col]
    else:
        country4 = country4.set_index('country_2')
        return country4['country']


# concepts
def cleanup_concepts(concepts, drop_placeholder=False):
    """rename the columns and remove placeholder from graphing settings data."""
    cs = concepts.copy()
    cs.columns = list(map(to_concept_id, cs.columns))
    cs['concept_type'] = 'measure'
    cs = cs.drop(['download'], axis=1)
    # Change below to cs.loc?
    cs = cs.loc[:, ['ddf_id', 'name', 'tooltip', 'menu_level1', 'menu_level_2',
                    'indicator_url', 'scale', 'ddf_name', 'ddf_unit', 'interpolation',
                    'concept_type']]
    cs = cs.rename(columns={'ddf_id': 'concept', 'name': 'full_name',
                            'ddf_name': 'name', 'ddf_unit': 'unit',
                            'tooltip': 'description'})
    if drop_placeholder:
        k = cs[cs.concept == u'———————————————————————'].index
        cs = cs.drop(k)

    return cs


def extract_concepts(cs, geo, gps, sgdc, mdata):
    """extract all concepts.

    cs: all measure type concepts, from graph_settings file.
    geo: country_synonyms.xlsx, contains all country info
    gps: area_categorizarion.json, contains groups name and group levels
    sgdc: discrete concept file from systema_globals
    mdata: metadata.json
    """
    concepts = cs.rename(columns={'ddf_id': 'Concept', 'Name': 'Full Name',
                                        'ddf_name':'Name', 'ddf_unit': 'Unit',
                                        'Tooltip': 'Description'}).copy()
    dsc = concepts.columns
    dsc = dsc.drop(['Download', 'Menu level1', 'Menu level 2', 'Scale'])

    concepts.columns = list(map(to_concept_id, concepts.columns))
    concepts['concept_type'] = 'measure'
    concepts = concepts.drop(['download'], axis=1)
    concepts = concepts.iloc[:, [5, 0, 1 , 2, 3, 4, 6, 7, 8, 9, 10]]
    cc = concepts[['concept', 'name', 'concept_type', 'description', 'indicator_url', 'scale', 'unit', 'interpolation']].copy()
    k = concepts[concepts.concept == u'———————————————————————'].index
    cc = cc.drop(k)
    cc['drill_up'] = np.nan
    cc['domain'] = np.nan
    cc['scales'] = cc['scale'].apply(lambda x: ['log', 'linear'] if x == 'log' else ['linear', 'log'])

    rm = {'gini': 'sg_gini',
          'population': 'sg_population',
          'gdp_p_cap_const_ppp2011_dollar': 'sg_gdp_p_cap_const_ppp2011_dollar'
    }

    cc2 = pd.DataFrame([], columns=cc.columns)
    cc2.concept = rm.values()
    cc2['name'] = cc2.concept
    cc2['concept_type'] = 'measure'
    cc2['indicator_url'] = cc2['concept'].apply(lambda x: mdata['indicatorsDB'][x[3:]]['sourceLink'])
    cc2['scales'] = cc2['concept'].apply(lambda x: mdata['indicatorsDB'][x[3:]]['scales'])

    dc = pd.DataFrame([], columns=cc.columns)
    dcl = list(map(to_concept_id, gps.n.values))

    geo = geo.rename(columns={'NAME': 'Upper Case Name', 'Use Name': 'Name'})
    ccs = geo.columns.drop(['Name', 'ISO3dig_ext'])
    ccs_id = list(map(to_concept_id, ccs))

    w4r_name = sgdc[sgdc['concept'] == 'world_4region']['name'].iloc[0]

    # make a list of all concepts.
    dcl_ = np.r_[dcl, ['geo', 'country','time', 'name', 'gwid', 'name_short', 'name_long', 'description'],
                 ccs_id, ['indicator_url', 'scales', 'unit', 'interpolation', 'world_4region', 'latitude', 'longitude', 'year', 'global']]
    dcl_2 = np.r_[gps.n.values, ['Geo', 'Country','Time', 'Name', 'Gwid', 'Name Short', 'Name Long', 'Description'],
                  ccs, ['Indicator Url', 'Scales', 'Unit', 'Interpolation', w4r_name, 'Latitude', 'Longitude', 'Year', 'World']]

    dc['concept'] = dcl_
    dc['name'] = dcl_2

    # TODO: maybe change hard code index to name comparing?
    dc['concept_type'] = 'string'
    dc.loc[:5, 'concept_type'] = 'entity_set'  # all groups
    dc.loc[:5, 'domain'] = 'geo'
    dc.loc[6, 'concept_type'] = 'entity_domain'  # geo
    dc.loc[7, 'concept_type'] = 'entity_set'  # country
    dc.loc[7, 'drill_up'] = dcl
    dc.loc[7, 'domain'] = 'geo'
    dc.loc[8, 'concept_type'] = 'time'  # time
    dc.loc[8, 'domain'] = 'year'
    dc.loc[36, 'concept_type'] = 'entity_set'  # world_4region
    dc.loc[36, 'domain'] = 'geo'
    dc.loc[[37,38], 'concept_type'] = 'measure'  # latitude and longitude
    dc.loc[[37,38], 'unit'] = 'degrees'
    dc.loc[37, 'scale'] = 'lat'
    dc.loc[38, 'scale'] = 'long'
    dc.loc[39, 'concept_type'] = 'time'  # year
    dc.loc[39, 'domain'] = 'time'
    dc.loc[40, 'domain'] = 'geo'  # global
    dc.loc[40, 'concept_type'] = 'entity_set'


    c_all = pd.concat([dc, cc, cc2])
    c_all = c_all.drop('scale', axis=1)

    return c_all


# Datapoints
def extract_datapoints(data_source, idt, concepts, geo, geomap):
    """yields each datapoint dataframe from files in indicators dir

    data_source: indicators data dir
    idt: DataFrame containing concept name and hashed file name.
    """
    geo_ = geo[['ISO3dig_ext', 'Gwid']]
    geo_ = geo_.set_index('Gwid')
    fs = os.listdir(data_source)
    for f in fs:
        if '.json' not in f:
            continue

        p = os.path.join(data_source, f)

        col = f[:-5]  # get indicator file name
        try:
            col_r = rename_col(col, idt, concepts)  # get indicator's id
        except:
            continue

        d = pd.read_json(p)

        if 'geo' in d.columns:
            d['geo'] = rename_geo(d['geo'], geo_, geomap)
            d = d.rename(columns={col: col_r})
            yield (col_r, d)
        else:  # it's empty.
            continue

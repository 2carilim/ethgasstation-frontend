import time
import sys
import json
import math
import traceback
import os
import pandas as pd
import numpy as np
from web3 import Web3, HTTPProvider
from sqlalchemy import create_engine, Column, Integer, String, DECIMAL, BigInteger, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from egs_ref import *

web3 = Web3(HTTPProvider('http://localhost:8545'))
engine = create_engine(
    'mysql+mysqlconnector://ethgas:station@127.0.0.1:3306/tx', echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

   

def init_dfs():
    """load data from mysql"""
    blockdata = pd.read_sql('SELECT * from blockdata2 order by id desc limit 2000', con=engine)
    blockdata = blockdata.drop('id', axis=1)
    postedtx = pd.read_sql('SELECT * from postedtx2 order by id desc limit 100000', con=engine)
    minedtx = pd.read_sql('SELECT * from minedtx2 order by id desc limit 100000', con=engine)
    minedtx.set_index('index', drop=True, inplace=True)
    alltx = postedtx[['index', 'expectedTime', 'expectedWait', 'mined_probability', 'highgas2', 'from_address', 'gas_offered', 'gas_price', 'hashpower_accepting', 'num_from', 'num_to', 'ico', 'dump', 'high_gas_offered', 'pct_limit', 'round_gp_10gwei', 'time_posted', 'block_posted', 'to_address', 'tx_atabove', 'wait_blocks', 'chained', 'nonce']].join(minedtx[['block_mined', 'miner', 'time_mined', 'removed_block']], on='index', how='left')
    alltx.set_index('index', drop=True, inplace=True)
    return(blockdata, alltx)

def prune_data(blockdata, alltx, txpool, block):
    """keep dataframes and databases from getting too big"""
    stmt = text("DELETE FROM postedtx2 WHERE block_posted <= :block")
    stmt2 = text("DELETE FROM minedtx2 WHERE block_mined <= :block")
    deleteBlock = block-2000
    engine.execute(stmt, block=deleteBlock)
    engine.execute(stmt2, block=deleteBlock)
    alltx = alltx.loc[alltx['block_posted'] > deleteBlock]
    blockdata = blockdata.loc[blockdata['block_number'] > deleteBlock]
    txpool = txpool.loc[txpool['block'] > (block-5)]
    return (blockdata, alltx, txpool)

def write_to_sql(alltx, analyzed_block, block_sumdf, mined_blockdf_seen, block):
    """write data to mysql for analysis"""
    post = alltx[alltx.index.isin(mined_blockdf_seen.index)]
    post.to_sql(con=engine, name='minedtx2', if_exists='append', index=True)
    print ('num mined = ' + str(len(post)))
    post2 = alltx.loc[alltx['block_posted'] == (block-1)]
    post2.to_sql(con=engine, name='postedtx2', if_exists='append', index=True)
    print ('num posted = ' + str(len(post2)))
    analyzed_block.to_sql(con=engine, name='txpool_current', index=False, if_exists='replace')
    block_sumdf.to_sql(con=engine, name='blockdata2', if_exists='append', index=False)


def write_to_json(gprecs, txpool_by_gp, prediction_table, analyzed_block):
    """write json data"""
    try:
        txpool_by_gp = txpool_by_gp.rename(columns={'gas_price':'count'})
        txpool_by_gp['gasprice'] = txpool_by_gp['round_gp_10gwei']/10
        txpool_by_gp['gas_offered'] = txpool_by_gp['gas_offered']/1e6
        prediction_table['gasprice'] = prediction_table['gasprice']/10
        analyzed_block_show  = analyzed_block.loc[analyzed_block['chained']==0].copy()
        analyzed_block_show['gasprice'] = analyzed_block_show['round_gp_10gwei']/10
        analyzed_block_show = analyzed_block_show[['index', 'block_posted', 'gas_offered', 'gasprice', 'hashpower_accepting', 'tx_atabove', 'mined_probability', 'expectedWait', 'wait_blocks']].sort_values('wait_blocks', ascending=False)
        analyzed_blockout = analyzed_block_show.to_json(orient='records')
        prediction_tableout = prediction_table.to_json(orient='records')
        txpool_by_gpout = txpool_by_gp.to_json(orient='records')
        parentdir = os.path.dirname(os.getcwd())
        filepath_gprecs = parentdir + '/json/ethgasAPI.json'
        filepath_txpool_gp = parentdir + '/json/memPool.json'
        filepath_prediction_table = parentdir + '/json/predictTable.json'
        filepath_analyzedblock = parentdir + '/json/txpoolblock.json'
        with open(filepath_gprecs, 'w') as outfile:
            json.dump(gprecs, outfile)

        with open(filepath_prediction_table, 'w') as outfile:
            outfile.write(prediction_tableout)

        with open(filepath_txpool_gp, 'w') as outfile:
            outfile.write(txpool_by_gpout)

        with open(filepath_analyzedblock, 'w') as outfile:
            outfile.write(analyzed_blockout)
    
    except Exception as e:
        print(e)
    
def get_txhases_from_txpool(block):
    """gets list of all txhash in txpool at block and returns dataframe"""
    hashlist = []
    txpoolcontent = web3.txpool.content
    txpoolpending = txpoolcontent['pending']
    for tx_sequence in txpoolpending.values():
        for tx_obj in tx_sequence.values():
            hashlist.append(tx_obj['hash'])
    txpool_current = pd.DataFrame(index = hashlist)
    txpool_current['block'] = block
    return txpool_current

def process_block_transactions(block, timer):
    """get tx data from block"""
    block_df = pd.DataFrame()
    block_obj = web3.eth.getBlock(block, True)
    miner = block_obj.miner 
    for transaction in block_obj.transactions:
        clean_tx = CleanTx(transaction, None, None, miner)
        block_df = block_df.append(clean_tx.to_dataframe(), ignore_index = False)
    block_df['time_mined'] = block_obj.timestamp
    return(block_df, block_obj)

def process_block_data(block_df, block_obj):
    """process block to dataframe"""
    if len(block_obj.transactions) > 0:
        block_df['weighted_fee'] = block_df['round_gp_10gwei']* block_df['gas_offered']
        block_mingasprice = block_df['round_gp_10gwei'].min()
        block_weightedfee = block_df['weighted_fee'].sum() / block_df['gas_offered'].sum()
    else:
        block_mingasprice = np.nan
        block_weightedfee = np.nan
    block_numtx = len(block_obj.transactions)
    timemined = block_df['time_mined'].min()
    clean_block = CleanBlock(block_obj, 1, 0, timemined, block_mingasprice, block_numtx, block_weightedfee)
    return(clean_block.to_dataframe())

def get_hpa(gasprice, hashpower):
    """gets the hash power accpeting the gas price over last 200 blocks"""
    hpa = hashpower.loc[gasprice >= hashpower.index, 'hashp_pct']
    if gasprice > hashpower.index.max():
        hpa = 100
    elif gasprice < hashpower.index.min():
        hpa = 0
    else:
        hpa = hpa.max()
    return int(hpa)

def get_tx_atabove(gasprice, txpool_by_gp):
    """gets the number of transactions in the txpool at or above the given gasprice"""
    txAtAb = txpool_by_gp.loc[txpool_by_gp.index >= gasprice, 'gas_price']
    if gasprice > txpool_by_gp.index.max():
        txAtAb = 0
    else:
        txAtAb = txAtAb.sum()
    return txAtAb

def predict(row):
    if row['chained'] == 1:
        return np.nan
    intercept = 3.3381
    hpa_coef = -0.0172
    txatabove_coef= 0.001
    interact_coef = 0
    high_gas_coef = 1.6907
    try:
        sum1 = (intercept + (row['hashpower_accepting']*hpa_coef) + (row['tx_atabove']*txatabove_coef) + (row['hgXhpa']*interact_coef) + (row['highgas2']*high_gas_coef))
        prediction = np.exp(sum1)
        if prediction < 2:
            prediction = 2
        if row['gas_offered'] > 2000000:
            prediction = prediction + 100
        return np.round(prediction, decimals=2)
    except Exception as e:
        print(e)
        return np.nan


def analyze_last200blocks(block, blockdata):
    recent_blocks = blockdata.loc[blockdata['block_number'] > (block-200), ['mingasprice', 'block_number', 'gaslimit', 'time_mined', 'speed']]
    gaslimit = recent_blocks['gaslimit'].mean()
    last10 = recent_blocks.sort_values('block_number', ascending=False).head(n=10)
    speed = last10['speed'].mean()
    #create hashpower accepting dataframe based on mingasprice accepted in block
    hashpower = recent_blocks.groupby('mingasprice').count()
    hashpower = hashpower.rename(columns={'block_number': 'count'})
    hashpower['cum_blocks'] = hashpower['count'].cumsum()
    totalblocks = hashpower['count'].sum()
    hashpower['hashp_pct'] = hashpower['cum_blocks']/totalblocks*100
    #get avg blockinterval time
    blockinterval = recent_blocks.sort_values('block_number').diff()
    blockinterval.loc[blockinterval['block_number'] > 1, 'time_mined'] = np.nan
    blockinterval.loc[blockinterval['time_mined']< 0, 'time_mined'] = np.nan
    avg_timemined = blockinterval['time_mined'].mean()
    if np.isnan(avg_timemined):
        avg_timemined = 30
    return(hashpower, avg_timemined, gaslimit, speed)


def analyze_txpool(block, txpool, alltx, hashpower, avg_timemined, gaslimit):
    """gets txhash from all transactions in txpool at block and merges the data from alltx"""
    #get txpool hashes at block
    txpool_block = txpool.loc[txpool['block']==block]
    if (len(txpool_block)==0):
        return(pd.DataFrame(), None, None)
    txpool_block = txpool_block.drop(['block'], axis=1)
    #merge transaction data for txpool transactions
    #txpool_block only has transactions received by filter
    txpool_block = txpool_block.join(alltx, how='inner')
    
    txpool_block = txpool_block[~txpool_block.index.duplicated(keep = 'first')]
    assert txpool_block.index.duplicated(keep='first').sum() == 0

    txpool_block['num_from'] = txpool_block.groupby('from_address')['block_posted'].transform('count')
    txpool_block['num_to'] = txpool_block.groupby('to_address')['block_posted'].transform('count')
    txpool_block['ico'] = (txpool_block['num_to'] > 90).astype(int)
    txpool_block['dump'] = (txpool_block['num_from'] > 5).astype(int)
    #group by gasprice
    txpool_by_gp = txpool_block[['gas_price', 'round_gp_10gwei']].groupby('round_gp_10gwei').agg({'gas_price':'count'})
    txpool_block_nonce = txpool_block[['from_address', 'nonce']].groupby('from_address').agg({'nonce':'min'})

    #predictiontable
    predictTable = pd.DataFrame({'gasprice' :  range(10, 1010, 10)})
    ptable2 = pd.DataFrame({'gasprice' : range(0, 10, 1)})
    predictTable = predictTable.append(ptable2).reset_index(drop=True)
    predictTable = predictTable.sort_values('gasprice').reset_index(drop=True)
    predictTable['hashpower_accepting'] = predictTable['gasprice'].apply(get_hpa, args=(hashpower,))
    predictTable['tx_atabove'] = predictTable['gasprice'].apply(get_tx_atabove, args=(txpool_by_gp,))
    predictTable['ico'] = 0
    predictTable['dump'] = 0
    predictTable['gas_offered'] = 0
    predictTable['wait_blocks'] = 0
    predictTable['highgas2'] = 0
    predictTable['chained'] = 0
    predictTable['hgXhpa'] = 0
    predictTable['wait_blocks'] = 0
    predictTable['expectedWait'] = predictTable.apply(predict, axis=1)
    predictTable['expectedTime'] = predictTable['expectedWait'].apply(lambda x: np.round((x * avg_timemined / 60), decimals=2))
    gp_lookup = predictTable.set_index('gasprice')['hashpower_accepting'].to_dict()
    txatabove_lookup = predictTable.set_index('gasprice')['tx_atabove'].to_dict()

    #finally, analyze txpool transactions
    print('txpool block length ' + str(len(txpool_block)))
    txpool_block['pct_limit'] = txpool_block['gas_offered'].apply(lambda x: x / gaslimit)
    txpool_block['high_gas_offered'] = (txpool_block['pct_limit']> .037).astype(int)
    txpool_block['highgas2'] = (txpool_block['pct_limit'] > .15).astype(int)
    txpool_block['hashpower_accepting'] = txpool_block['round_gp_10gwei'].apply(lambda x: gp_lookup[x] if x in gp_lookup else 100)
    txpool_block['hgXhpa'] = txpool_block['highgas2']*txpool_block['hashpower_accepting']
    txpool_block['tx_atabove'] = txpool_block['round_gp_10gwei'].apply(lambda x: txatabove_lookup[x] if x in txatabove_lookup else 1)
    txpool_block['expectedWait'] = txpool_block.apply(predict, axis=1)
    txpool_block['expectedTime'] = txpool_block['expectedWait'].apply(lambda x: np.round((x * avg_timemined / 60), decimals=2))
    txpool_by_gp = txpool_block[['wait_blocks', 'gas_offered', 'gas_price', 'round_gp_10gwei']].groupby('round_gp_10gwei').agg({'wait_blocks':'median','gas_offered':'sum', 'gas_price':'count'})
    txpool_by_gp.reset_index(inplace=True, drop=False)
    return(txpool_block, txpool_by_gp, predictTable)

def get_gasprice_recs(prediction_table, block_time, block, speed, minlow=-1):
    
    def get_safelow(minlow):
        series = prediction_table.loc[prediction_table['expectedTime'] <= 10, 'gasprice']
        safelow = series.min()
        minhash_list = prediction_table.loc[prediction_table['hashpower_accepting']>=1.5, 'gasprice']
        if (safelow < minhash_list.min()):
            safelow = minhash_list.min()
        if minlow >= 0:
            if safelow < minlow:
                safelow = minlow
        return float(safelow)

    def get_average():
        series = prediction_table.loc[prediction_table['expectedTime'] <= 4, 'gasprice']
        average = series.min()
        minhash_list = prediction_table.loc[prediction_table['hashpower_accepting']>35, 'gasprice']
        if average < minhash_list.min():
            average= minhash_list.min()
        return float(average)

    def get_fast():
        series = prediction_table.loc[prediction_table['expectedTime'] <= 1, 'gasprice']
        fastest = series.min()
        minhash_list = prediction_table.loc[prediction_table['hashpower_accepting']>90, 'gasprice']
        if fastest < minhash_list.min():
            fastest = minhash_list.min()
        if np.isnan(fastest):
            fastest = 1000
        return float(fastest)

    def get_fastest():
        fastest = prediction_table['expectedTime'].min()
        series = prediction_table.loc[prediction_table['expectedTime'] == fastest, 'gasprice']
        fastest = series.min()
        minhash_list = prediction_table.loc[prediction_table['hashpower_accepting']>95, 'gasprice']
        if fastest < minhash_list.min():
            fastest = minhash_list.min()
        return float(fastest) 

    def get_wait(gasprice):
        try:
            wait =  prediction_table.loc[prediction_table['gasprice']==gasprice, 'expectedTime'].values[0]
        except:
            wait = 0
        wait = round(wait, 1)
        return float(wait)
    
    gprecs = {}
    gprecs['safeLow'] = get_safelow(minlow)
    gprecs['safeLowWait'] = get_wait(gprecs['safeLow'])
    gprecs['average'] = get_average()
    gprecs['avgWait'] = get_wait(gprecs['average'])
    gprecs['fast'] = get_fast()
    gprecs['fastWait'] = get_wait(gprecs['fast'])
    gprecs['fastest'] = get_fastest()
    gprecs['fastestWait'] = get_wait(gprecs['fastest'])
    gprecs['block_time'] = block_time
    gprecs['blockNum'] = block
    gprecs['speed'] = speed
    return(gprecs)


def master_control():
    (blockdata, alltx) = init_dfs()
    txpool = pd.DataFrame()
    snapstore = pd.DataFrame()
    print ('blocks '+ str(len(blockdata)))
    print ('txcount '+ str(len(alltx)))
    timer = Timers(web3.eth.blockNumber)  
    start_time = time.time()
    tx_filter = web3.eth.filter('pending')

    
    def append_new_tx(clean_tx):
        nonlocal alltx
        if not clean_tx.hash in alltx.index:
            alltx = alltx.append(clean_tx.to_dataframe(), ignore_index = False)
    


    def update_dataframes(block):
        nonlocal alltx
        nonlocal txpool
        nonlocal blockdata
        nonlocal snapstore
        nonlocal timer

        print('updating dataframes at block '+ str(block))
        try:
            #get minedtransactions and blockdata from previous block
            mined_block_num = block-3
            (mined_blockdf, block_obj) = process_block_transactions(mined_block_num, timer)

            #add mined data to tx dataframe - only unique hashes seen by node
            mined_blockdf_seen = mined_blockdf[mined_blockdf.index.isin(alltx.index)]
            print('num mined in ' + str(mined_block_num)+ ' = ' + str(len(mined_blockdf)))
            print('num seen in ' + str(mined_block_num)+ ' = ' + str(len(mined_blockdf_seen)))
            alltx = alltx.combine_first(mined_blockdf_seen)

            #process block data
            block_sumdf = process_block_data(mined_blockdf, block_obj)

            #add block data to block dataframe 
            blockdata = blockdata.append(block_sumdf, ignore_index = True)

            #get list of txhashes from txpool 
            current_txpool = get_txhases_from_txpool(block)

            #add txhashes to txpool dataframe
            txpool = txpool.append(current_txpool, ignore_index = False)

            #get hashpower table, block interval time, gaslimit, speed from last 200 blocks
            (hashpower, block_time, gaslimit, speed) = analyze_last200blocks(block, blockdata)

            #make txpool block data
            (analyzed_block, txpool_by_gp, predictiondf) = analyze_txpool(block-1, txpool, alltx, hashpower, block_time, gaslimit)
            if analyzed_block.empty:
                print("txpool block is empty - returning")
                return
            assert analyzed_block.index.duplicated().sum()==0
            alltx = alltx.combine_first(analyzed_block)

            #with pd.option_context('display.max_columns', None,):
                #print(analyzed_block)
            # update tx dataframe with txpool variables and time preidctions

            #get gpRecs
            gprecs = get_gasprice_recs (predictiondf, block_time, block, speed, timer.minlow)

            #every block, write gprecs, predictions, txpool by gasprice
            analyzed_block.reset_index(drop=False, inplace=True)
            write_to_json(gprecs, txpool_by_gp, predictiondf, analyzed_block)
            write_to_sql(alltx, analyzed_block, block_sumdf, mined_blockdf_seen, block)

            #keep from getting too large
            (blockdata, alltx, txpool) = prune_data(blockdata, alltx, txpool, block)
            return True

        except: 
            print(traceback.format_exc())    

    
    while True:
        try:
            new_tx_list = web3.eth.getFilterChanges(tx_filter.filter_id)
        except:
            tx_filter = web3.eth.filter('pending')
            new_tx_list = web3.eth.getFilterChanges(tx_filter.filter_id)
        block = web3.eth.blockNumber
        timestamp = time.time()
        if (timer.process_block > (block - 5)):
            for new_tx in new_tx_list:    
                try:        
                    tx_obj = web3.eth.getTransaction(new_tx)
                    clean_tx = CleanTx(tx_obj, block, timestamp)
                    append_new_tx(clean_tx)
                except Exception as e:
                    pass
        if (timer.process_block < block):
   
            if block > timer.start_block+1:
                print('current block ' +str(block))
                print ('processing block ' + str(timer.process_block))
                updated = update_dataframes(timer.process_block)
                print('finished processing')
                timer.process_block = timer.process_block + 1
    
    
            

master_control()

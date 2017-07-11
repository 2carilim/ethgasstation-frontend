#Reports on mempool wait times and miner gas mined on last block and votes on gas limit

import mysql.connector, sys, os
import pandas as pd
import numpy as np
import subprocess, json
import os, subprocess, re
import urllib

endBlock = int(sys.argv[1])
callTime = int(sys.argv[2])




dictMiner = {
    '0xea674fdde714fd979de3edf0f56aa9716b898ec8':'Ethermine',
    '0x1e9939daaad6924ad004c2560e90804164900341':'ethfans',
    '0xb2930b35844a230f00e51431acae96fe543a0347':'miningpoolhub',
    '0x4bb96091ee9d802ed039c4d1a5f6216f90f81b01':'Ethpool',
    '0x52bc44d5378309ee2abf1539bf71de1b7d7be3b5':'Nanopool',
    '0x2a65aca4d5fc5b5c859090a6c34d164135398226':'Dwarfpool',
    '0x829bd824b016326a401d083b33d092293333a830':'f2pool',
    '0xa42af2c70d316684e57aefcc6e393fecb1c7e84e':'Coinotron',
    '0x6c7f03ddfdd8a37ca267c88630a4fee958591de0':'alpereum'

}

try:
    url = "http://localhost/json/price.json"
    response = urllib.urlopen(url)
    hashPower = pd.read_json(response, orient='records')
    response.close()
except:
    print ('error')

print (hashPower)

try:
    url = "http://localhost/json/ethgas.json"
    response = urllib.urlopen(url)
    calc = json.load(response)
    response.close()
except:
    print ('error')


#load mempool and most recent block transactions

cnx = mysql.connector.connect(user='ethgas', password='station', host='127.0.0.1', database='tx')
cursor = cnx.cursor()

cursor.execute("SELECT txHash FROM txpool2 WHERE block = %s" % endBlock)
head = cursor.column_names
txpool = pd.DataFrame(cursor.fetchall())
txpool.columns = head
txpoolList = txpool['txHash'].values.astype(str)
txpoolList2 = txpoolList.tolist()

query = "SELECT txHash, gasPrice, gasOffered, postedBlock, tsPosted from transactions where txHash IN (%s)" % ','.join("'" + item + "'" for item in txpoolList2)
cursor.execute(query)
head = cursor.column_names
memPoolTx = pd.DataFrame(cursor.fetchall())
memPoolTx.columns = head
memPoolTx['tx'] = 1
memPoolTx['gasPrice'] = memPoolTx['gasPrice'].apply(lambda x: x/float(1000))
memPoolTx['gasPrice'] = memPoolTx['gasPrice'].apply(lambda x: np.round(x, decimals=0) if x >=1 else np.round(x, decimals=3))
memPoolTx['waitBlocks'] = memPoolTx['postedBlock'].apply(lambda x: endBlock-x)
memPoolTx['waitTime'] = memPoolTx['tsPosted'].apply(lambda x: callTime-x)
memPoolTx['gasOffered'] = memPoolTx['gasOffered'].apply(lambda x: x/1e6)

memPool = memPoolTx.groupby('gasPrice').sum().reset_index()

memPool = memPool.drop(['postedBlock', 'tsPosted', 'waitBlocks', 'waitTime'], axis=1)
memPool['gasOffered'] = memPool['gasOffered'].apply(lambda x: np.round(x, decimals=2))

memPoolAvg = memPoolTx.groupby('gasPrice').mean().reset_index()
memPoolAvg = memPoolAvg.drop(['postedBlock', 'tsPosted', 'gasOffered', 'gasPrice', 'tx'], axis=1)
memPoolAvg['waitTime'] = memPoolAvg['waitTime'].apply(lambda x: np.round(x, decimals=0))
memPoolAvg['waitBlocks'] = memPoolAvg['waitBlocks'].apply(lambda x: np.round(x, decimals=2))

memPool = pd.concat([memPool, memPoolAvg], axis = 1)
memPool = memPool.fillna(value=0)

print (memPool)

n=100
k=10
predictTable = pd.DataFrame({'gasPrice' :  range(1, n+1, 1)})
ptable2 = pd.DataFrame({'gasPrice' : [0, .1, .2, .3, .4 , .5, .6, .7, .8 , .9]})
predictTable = predictTable.append(ptable2).reset_index(drop=True)
predictTable = predictTable.sort_values('gasPrice').reset_index(drop=True)



def getHashPowerAccepting (gasPrice):
    lower = hashPower.loc[hashPower['adjustedMinP'] <= gasPrice, 'cumPctTotBlocks']
    return (lower.max())

def txAbove (gasPrice):
    seriesTxAbove = memPool.loc[memPool['gasPrice'] > gasPrice, 'tx']
    return (seriesTxAbove.sum())

def txAt (gasPrice):
    seriesTxAt = memPool.loc[memPool['gasPrice'] == gasPrice, 'tx']
    return (seriesTxAt.sum())


for index, row in predictTable.iterrows():
    predictTable.loc[index, 'hashPowerAccepting'] = getHashPowerAccepting(row['gasPrice'])
    predictTable.loc[index, 'txAbove'] = txAbove(row['gasPrice'])
    predictTable.loc[index, 'txAt'] = txAt(row['gasPrice'])

totalTxTxP = memPool['tx'].sum()
predictTable['congestedCont'] = totalTxTxP/float(calc['gasLimit'])
predictTable['congestedcontXtxabove'] = predictTable['congestedCont']*predictTable['txAbove']
predictTable['transfer']=1

#model Parameters

predictTable['intercept'] = 3.2905
predictTable['hashPowerCoef'] = -0.0244
predictTable['tfercoef'] = -.7511
predictTable['congcontcoef'] = 3332.6756
predictTable['congcontXtx'] = .3288
predictTable['txAbovecoeff'] = -0.0008
predictTable['txAtcoeff'] = 0.0004

predictTable['sum'] = predictTable['intercept'] + (predictTable['hashPowerAccepting']*predictTable['hashPowerCoef']) + (predictTable['transfer']*predictTable['tfercoef']) + (predictTable['congestedCont'] * predictTable['congcontcoef']) + (predictTable['congestedcontXtxabove'] * predictTable['congcontXtx']) + (predictTable['txAbove']* predictTable['txAbovecoeff']) + (predictTable['txAt'] * predictTable['txAtcoeff'])

predictTable['sumC'] = predictTable['intercept'] + (predictTable['hashPowerAccepting']*predictTable['hashPowerCoef']) + (predictTable['congestedCont'] * predictTable['congcontcoef']) + (predictTable['congestedcontXtxabove'] * predictTable['congcontXtx']) + (predictTable['txAbove']* predictTable['txAbovecoeff']) + (predictTable['txAt'] * predictTable['txAtcoeff'])

predictTable['expectedWait'] = predictTable['sum'].apply(lambda x: np.exp(x))
predictTable['expectedWait'] = predictTable['expectedWait'].apply(lambda x: 2 if (x < 2) else x)
predictTable['expectedTime'] = predictTable['expectedWait'].apply(lambda x: x * calc['blockInterval']/60)

predictTable['expectedWaitC'] = predictTable['sumC'].apply(lambda x: np.exp(x))
predictTable['expectedWaitC'] = predictTable['expectedWaitC'].apply(lambda x: 2 if (x < 2) else x)
predictTable['expectedTimeC'] = predictTable['expectedWaitC'].apply(lambda x: x * calc['blockInterval']/60)

print(predictTable)

def getSafeLow():
    series = predictTable.loc[predictTable['expectedTime'] <= 15, 'gasPrice']
    safeLow = series.min()
    minHashList = hashPower.loc[hashPower['cumPctTotBlocks']>2, 'adjustedMinP'].values
    if (safeLow < minHashList.min()):
        safeLow = minHashList.min()
    if (safeLow < calc['minLow']):
        safeLow = calc['minLow']
    return safeLow

def getAverage():
    series = predictTable.loc[predictTable['expectedTime'] <= 5, 'gasPrice']
    average = series.min()
    minHashList = hashPower.loc[hashPower['cumPctTotBlocks']>=50, 'adjustedMinP'].values
    if (average < minHashList.min()):
        average= minHashList.min()
    return average

def getFastest():
    series = predictTable.loc[predictTable['expectedWait'] <= 2, 'gasPrice']
    fastest = series.min()
    if (fastest == np.nan):
        fastest = 100
    return fastest

def getWait(gasPrice):
    if gasPrice<1:
        gasPrice = np.round(gasPrice, 1)
    else:
        gasPrice = np.round(gasPrice, 0)
    if gasPrice < .1:
        gasPrice = .1
    wait = round(predictTable.loc[predictTable['gasPrice'] == gasPrice, 'expectedTime'].values[0], 1)
    return wait

def getConWait(gasPrice):
    if gasPrice<1:
        gasPrice = np.round(gasPrice, 1)
    else:
        gasPrice = np.round(gasPrice, 0)
    if gasPrice < .1:
        gasPrice = .1
    wait = round(predictTable.loc[predictTable['gasPrice'] == gasPrice, 'expectedTimeC'].values[0], 1)
    return wait

calc2 = {}
calc2['safeLow'] = getSafeLow()
calc2['safeLowWait'] = getWait(calc2['safeLow'])
calc2['average'] = getAverage()
calc2['avgWait'] = getWait(calc2['average'])
calc2['fastest'] = getFastest()
calc2['fastWait'] = getWait(calc2['fastest'])
calc2['safeLowWaitC'] = getConWait(calc2['safeLow'])
calc2['avgWaitC'] = getConWait(calc2['average'])
calc2['fastWaitC'] = getConWait(calc2['fastest'])
calc2['blockNum'] = endBlock
print(calc2)


memPoolTable = memPool.to_json(orient = 'records')
parentdir = os.path.dirname(os.getcwd())
if not os.path.exists(parentdir + '/json'):
    os.mkdir(parentdir + '/json')
filepath_gpRecs2 = parentdir + '/json/ethgasAPI.json'
filepath_memPool = parentdir + '/json/memPool.json'


with open(filepath_gpRecs2, 'w') as outfile:
    json.dump(calc2, outfile)

with open(filepath_memPool, 'w') as outfile:
    outfile.write(memPoolTable)


#analysis:  Run poission regression models

import mysql.connector
import pandas as pd
import numpy as np 
import statsmodels.api as sm
import math
import sys
import os, subprocess, re
import urllib,json
from sqlalchemy import create_engine 
from patsy import dmatrices

cnx = mysql.connector.connect(user='ethgas', password='station', host='127.0.0.1', database='tx')
cursor = cnx.cursor()

'''
#run this the fist time to make complete dataset
query = ("SELECT prediction6.*, minedtransactions.minedBlock, minedtransactions.gasused FROM prediction6 LEFT JOIN minedtransactions ON prediction6.txHash = minedtransactions.txHash")
engine = create_engine('mysql+mysqlconnector://ethgas:station@127.0.0.1:3306/tx', echo=False)


cursor.execute(query)
head = cursor.column_names
predictData = pd.DataFrame(cursor.fetchall())
predictData.columns = head

compStart = 0
compEnd = 20000
ints = int(len(predictData)/20000)
print ('ints ' + str(ints)) 
for x in range (0, ints):
    predict1 = pd.DataFrame(predictData.iloc[compStart:compEnd, :])
    predict1.to_sql(con=engine, name = 'prediction6complete', if_exists='append', index=True)
    compStart = compStart + 20000
    compEnd = compEnd + 20000
print('compEnd ' + str(compEnd))
predict1 = pd.DataFrame(predictData.iloc[compStart:, :])
predict1.to_sql(con=engine, name = 'prediction6complete', if_exists='append', index=True) 


query = ("SELECT * FROM prediction6complete")
cursor.execute(query)
head = cursor.column_names
predictData = pd.DataFrame(cursor.fetchall())
predictData.columns = head


predictData = predictData.drop('totalTxFee', axis=1)

query = ("SELECT * FROM prediction5complete")
cursor.execute(query)
head = cursor.column_names
predictData2 = pd.DataFrame(cursor.fetchall())
predictData2.columns = head


predictData2.drop('ageAt', axis=1, inplace=True)

predictData = predictData.append(predictData2).reset_index(drop=True)

print('total transactions:')
print(len(predictData))
print('total confirmed transactions:')
print(predictData['minedBlock'].count())

predictData['confirmTime'] = predictData['minedBlock']-predictData['postedBlock']


print('zero/neg confirm times: ')
print(predictData[predictData['confirmTime']<=0].count())

predictData[predictData['confirmTime'] <= 0] = np.nan
predictData['dump'] = predictData['numFrom'].apply(lambda x: 1 if x>5 else 0)
predictData.loc[predictData['confirmTime'] >= 200, 'confirmTime'] = 200
predictData = predictData.dropna(how='any')
predictData['txAtAbove'] = predictData['txAt'] + predictData['txAbove']

#combine and save
engine = create_engine('mysql+mysqlconnector://ethgas:station@127.0.0.1:3306/tx', echo=False) 
compStart = 0
compEnd = 20000
ints = int(len(predictData)/20000)
print ('ints ' + str(ints)) 
for x in range (0, ints):
    predict1 = pd.DataFrame(predictData.iloc[compStart:compEnd, :])
    predict1.to_sql(con=engine, name = 'predictionCombined', if_exists='append', index=True)
    compStart = compStart + 20000
    compEnd = compEnd + 20000
print('compEnd ' + str(compEnd))
predict1 = pd.DataFrame(predictData.iloc[compStart:, :])
predict1.to_sql(con=engine, name = 'predictionCombined', if_exists='append', index=True) 
'''

query = ("SELECT * FROM predictionCombined")
cursor.execute(query)
head = cursor.column_names
predictData = pd.DataFrame(cursor.fetchall())
predictData.columns = head
predictData.loc[predictData['totalTxTxP']==0, 'confirmTime'] = np.nan
predictData['ico'] = predictData['numTo'].apply(lambda x: 1 if x>100 else 0)
predictData = predictData.dropna(how='any')
cursor.close()

print ('cleaned transactions: ')
print (len(predictData))

#print(predictData)

predictData['logCTime'] = predictData['confirmTime'].apply(np.log)
predictData['transfer'] = predictData['gasOffered'].apply(lambda x: 1 if x ==21000 else 0) 

print ('numTo median:')
print (predictData['numTo'].quantile(.5))

print ('numTo 95%')
print (predictData['numTo'].quantile(.95))




avgGasLimit = predictData.loc[0, 'gasOffered'] / predictData.loc[0, 'gasOfferedPct']
transactionGas = float(21000)/avgGasLimit

quantiles= predictData['gasOfferedPct'].quantile([.5, .75, .9, 1])
print (transactionGas)
print(quantiles)

#dep['gasCat1'] = (txData2['gasused'] == 21000).astype(int)
predictData['gasCat2'] = ((predictData['gasOfferedPct']>transactionGas) & (predictData['gasOfferedPct']<=quantiles[.75])).astype(int)
predictData['gasCat3'] = ((predictData['gasOfferedPct']>quantiles[.75]) & (predictData['gasOfferedPct']<=quantiles[.9])).astype(int)
predictData['gasCat4'] = (predictData['gasOfferedPct']> quantiles[.9]).astype(int)

print('median gasOfferedPct')
print(transactionGas)
print(quantiles[.5])

print('confirmTImes')
print(predictData['confirmTime'].min())
print(predictData['confirmTime'].max())

print('hashPowerAccepting')
print(predictData['hashPowerAccepting'].min())
print(predictData['hashPowerAccepting'].max())

print('gas above mean: ')
print(predictData['pctLimitGasAbove'].mean())

print('gas at mean: ')
print(predictData['pctLimitGasAt'].mean())

print('tx above mean: ')
print(predictData['txAbove'].mean())

print ('mean confirm low gas price : ')
lowMean = predictData.loc[(predictData['dump']==0) & (predictData['gasPrice'] < 1000), 'confirmTime']
print(lowMean.mean())
print('count:')
print(lowMean.count())

predictData['gp1'] = predictData['gasPrice'].apply(lambda x: 1 if x <500 else 0)
predictData['gp2'] = predictData['gasPrice'].apply(lambda x: 1 if (x >=500 and x<1000) else 0)
predictData['gp3'] = predictData['gasPrice'].apply(lambda x: 1 if (x >=1000 and x<4000) else 0)
predictData['gp4'] = predictData['gasPrice'].apply(lambda x: 1 if (x >=4000 and x<23000) else 0)
predictData['gp5'] = predictData['gasPrice'].apply(lambda x: 1 if x >=23000 else 0)

  
pdGp3 = predictData[predictData['gp3']==1]
pdGp4 = predictData[predictData['gp4']==1]
pdGp5 = predictData[predictData['gp5']==1]



y, X = dmatrices('confirmTime ~ dump + ico + txAtAbove', data = pdGp3, return_type = 'dataframe')

print(y[:5])
print(X[:5])

model = sm.GLM(y, X, family=sm.families.Poisson())
results = model.fit()
print (results.summary())


y['predict'] = results.predict()
y['gasPrice'] = predictData['gasPrice']
y['hashPowerAccepting'] = predictData['hashPowerAccepting']
y['txAbove'] = predictData['txAbove']
y['txAt'] = predictData['txAt']
y['numFrom'] = predictData['numFrom']
y['dump'] = predictData['dump']

print(y)

print (y.loc[(y['dump']==0) & (y['gasPrice'] < 1000), ['confirmTime', 'predict', 'gasPrice']])

a, B = dmatrices('confirmTime ~ dump + ico + txAtAbove', data = pdGp4, return_type = 'dataframe')


model = sm.GLM(a, B, family=sm.families.Poisson())
results = model.fit()
print (results.summary())

a['predict'] = results.predict()
print(a[:15])
print(B[:15])


c, D = dmatrices('confirmTime ~ dump + ico + txAtAbove', data = pdGp5, return_type = 'dataframe')



model = sm.GLM(c, D, family=sm.families.Poisson())
results = model.fit()
print (results.summary())

c['predict'] = results.predict()
print(c[:15])
print(D[:15])

e, F = dmatrices('confirmTime ~ gp1+ gp2+ gp3 + gp4 + dump + ico + txAtAbove', data = predictData, return_type = 'dataframe')



model = sm.GLM(e, F, family=sm.families.Poisson())
results = model.fit()
print (results.summary())

e['predict'] = results.predict()
print(e[:15])
print(F[:15])


y1, X1 = dmatrices('logCTime ~ gp1+ gp2+ gp3 + gp4 + txAt + dump + numTo + txAbove', data = predictData, return_type = 'dataframe')

print(y[:5])
print(X[:5])

model = sm.OLS(y1, X1)
results = model.fit()
print (results.summary())
y1['predict'] = results.predict()
y1['confirmTime'] = predictData['confirmTime']
y1['predictTime'] = y1['predict'].apply(lambda x: np.exp(x))


y2, X2 = dmatrices('logCTime ~ gp1 + gp2+ gp3 + gp4 + txAt + dump + txAt', data = predictData, return_type = 'dataframe')

print(y[:5])
print(X[:5])

model = sm.OLS(y2, X2)
results = model.fit()
print (results.summary())


y3, X3 = dmatrices('logCTime ~ hashPowerAccepting + txAtAbove + dump', data = predictData, return_type = 'dataframe')

print(y[:5])
print(X[:5])

model = sm.OLS(y3, X3)
results = model.fit()
print (results.summary())

'''
y4, X4 = dmatrices('logCTime ~ hashPowerAccepting + gasOffered', data = predictData, return_type = 'dataframe')

print(y[:5])
print(X[:5])

model = sm.OLS(y4, X4)
results = model.fit()
print (results.summary())





with pd.option_context('display.max_rows', 500, 'display.max_columns', None):

    print(y.loc[(y['gasPrice']==1000) & (y['transfer']==1),:])
    print(y.loc[(y['gasPrice']>=50000) & (y['transfer']==1),:])
 
'''

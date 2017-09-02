import mysql.connector
import pandas as pd
import numpy as np 
import statsmodels.api as sm
import math
import sys
import os, subprocess, re
import urllib,json
from sqlalchemy import create_engine 


cnx = mysql.connector.connect(user='ethgas', password='station', host='127.0.0.1', database='tx')
cursor = cnx.cursor()

query = ("SELECT * FROM prediction7complete")
cursor.execute(query)
head = cursor.column_names
predictData = pd.DataFrame(cursor.fetchall())
predictData.columns = head

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
predictData['txAtAbove'] = predictData['txAt'] + predictData['txAbove']
predictData.loc[predictData['totalTxTxP']==0, 'confirmTime'] = np.nan
predictData['ico'] = predictData['numTo'].apply(lambda x: 1 if x>100 else 0)
predictData['logCTime'] = predictData['confirmTime'].apply(np.log)
predictData['transfer'] = predictData['gasOffered'].apply(lambda x: 1 if x ==21000 else 0) 

predictData.loc[predictData['prediction']==np.nan, 'confirmTime'] = np.nan

predictData = predictData.dropna(how='any')


query = ("SELECT * FROM predictionCombined")
cursor.execute(query)
head = cursor.column_names
combData = pd.DataFrame(cursor.fetchall())
combData.columns = head

combData['logCTime'] = combData['confirmTime'].apply(np.log)
combData['transfer'] = combData['gasOffered'].apply(lambda x: 1 if x ==21000 else 0) 

print ('length prior to combine')
print (len(combData))

combData = combData.append(predictData)

print ('length after combine')
print (len(combData))

print (combData)
combData = combData.dropna(how='any')

print ('length after drop missing')
print (len(combData))

ddd
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


query = ("SELECT * FROM predictionCombined")
cursor.execute(query)
head = cursor.column_names
predictData = pd.DataFrame(cursor.fetchall())
predictData.columns = head
predictData.loc[predictData['totalTxTxP']==0, 'confirmTime'] = np.nan
predictData['ico'] = predictData['numTo'].apply(lambda x: 1 if x>100 else 0)
predictData = predictData.dropna(how='any')
cursor.close()
<?php

require_once 'common.php';

//get connection
$mysqli = new mysqli(DB_HOST, DB_USERNAME, DB_PASSWORD, DB_NAME);

if(!$mysqli){
	die("Connection failed: " . $mysqli->error);
}

//query to get data from the table

$query = "SELECT * FROM txDataLast10k ORDER BY id DESC LIMIT 1";
$result = $mysqli->query($query);
$row = $result->fetch_assoc();


// Get values for Misc transactions table

$latestblock = $row['latestblockNum'];
$ethprice = $row['ETHpriceUSD'];
$ethpriceEUR = $row['ETHpriceEUR'];
$ethpriceCNY = $row['ETHpriceCNY'];
$ethpriceGBP = $row['ETHpriceGBP'];

if(isset($_GET['curr']) && !empty($_GET['curr'])){
	$currency = $_GET['curr'];

} 
else {$currency = 'usd';}

if ($currency == 'usd'){
    $exchangeRate = $ethprice;
}
elseif ($currency == 'eur'){
    $exchangeRate = $ethpriceEUR;
}
elseif ($currency == 'cny'){
    $exchangeRate = $ethpriceCNY;
}
elseif ($currency == 'gbp'){
    $exchangeRate = $ethpriceGBP;
}

if ($currency == 'eur'){
	$currSymbol = '€';
}
elseif ($currency == 'cny'){
	$currSymbol = '¥'; 

}
elseif ($currency == 'gbp'){
	$currSymbol = '£';
}
else {
	$currSymbol = '$';
}




try{
    $profitRaw = get_json_file("profit.json");
    $profitTable = json_decode($profitRaw, true);
    $gasGuzzRaw = get_json_file("gasguzz.json");
    $gasGuzzTable = json_decode($gasGuzzRaw, true);
    $uncGraphRaw = get_json_file("uncGraph.json");
    $uncGraphData = json_decode($uncGraphRaw, true);

} catch (Exception $e) {
    echo 'waith for tables to be populated';
}

$dataString = '';
foreach ($uncGraphData as $point)
{
    $dataString = $dataString . '{x: ';
    $dataString = $dataString . $point['x'] . ', ';
    $dataString = $dataString . 'y: '. $point['y']. '},';

}
$dataString = rtrim($dataString,',');


//free memory associated with result
$result->close();

//close connection
$mysqli->close();




?>
<?php



//query to get data from the table


try{
$memPoolString = file_get_contents("http://localhost/json/memPool.json");
$memPoolArray = json_decode($memPoolString, true);

$voteString = file_get_contents("http://localhost/json/vote.json");
$voteArray = json_decode($voteString, true);

} catch (Exception $e){
	echo 'keep waiting';
}


?>
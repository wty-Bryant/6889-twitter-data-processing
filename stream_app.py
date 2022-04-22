from pyspark import SparkConf, SparkContext
from pyspark.streaming import StreamingContext
from pyspark.sql import Row, SQLContext
import sys
import requests
from socket import *


def aggregate_tags_count(new_values, total_sum):
    return sum(new_values) + (total_sum or 0)


def get_sql_context_instance(spark_context):
    if ('sqlContextSingletonInstance' not in globals()):
        globals()['sqlContextSingletonInstance'] = SQLContext(spark_context)
    return globals()['sqlContextSingletonInstance']


def process_rdd(time, rdd):
    print("----------- %s -----------" % str(time))
    try:
        # Get spark sql singleton context from the current context
        sql_context = get_sql_context_instance(rdd.context)
        print("Get spark sql singleton context from the current context ----------- %s -----------" % str(time))

        # convert the RDD to Row RDD
        row_rdd = rdd.map(lambda w: Row(word=w[0], word_count=w[1]))

        # create a DF from the Row RDD
        hashtags_df = sql_context.createDataFrame(row_rdd)

        # Register the dataframe as table
        hashtags_df.registerTempTable("hashtags")

        # get the top 10 hashtags from the table using SQL and print them
        hashtag_counts_df = sql_context.sql(
            "select word , word_count from hashtags where word like '#%'order by word_count desc limit 10")
        hashtag_counts_df.show()
        hashtag_counts_df.coalesce(1).write.format('com.databricks.spark.csv').mode('overwrite').option("header",
                                                                                                        "true").csv(
            "Users/liupeihan/Desktop/hashtag_file.csv")
        # hashtag_counts_df.to_csv('Users/liupeihan/Desktop/' + 'hashtag_file.csv', index=False)

        country_counts_df = sql_context.sql(
            "select word as country_code, word_count as tweet_count from hashtags where word like 'CC%'order by word_count desc limit 10")
        country_counts_df.show()
        country_counts_df.coalesce(1).write.format('com.databricks.spark.csv').mode('overwrite').option("header",
                                                                                                        "true").csv(
            "Users/liupeihan/Desktop/country_file.csv")


        device_df = sql_context.sql(
            "select word as device, word_count as device_count from hashtags where word like 'TS%'order by word_count desc limit 10")
        device_df.show()
        device_df.coalesce(1).write.format('com.databricks.spark.csv').mode('overwrite').option("header", "true").csv(
            "Users/liupeihan/Desktop/device_file.csv")

        # send_df_to_dashboard(device_df)
    except:
        pass
        # e = sys.exc_info()[0]
        # print("Error: %s" % e)

# def send_df_to_dashboard(df):
#     top_tags = [str(t.hashtag) for t in df.select("hashtag").collect()]
#     tags_count = [p.hashtag_count for p in df.select("hashtag_count").collect()]
#     url = 'http://127.0.0.1:8080/updateData'
#     request_data = {'label': str(top_tags), 'data': str(tags_count)}
#     response = requests.post(url, data=request_data)
    
    
# create spark configuration
conf = SparkConf()
conf.setAppName("TwitterStreamApp")

# create spark context with the above configuration
sc = SparkContext(conf=conf)
sc.setLogLevel("ERROR")

# create the Streaming Context from the above spark context with interval size 2 seconds
ssc = StreamingContext(sc, 2)

# setting a checkpoint to allow RDD recovery
ssc.checkpoint("checkpoint_TwitterApp")

# read data from port 9009
dataStream = ssc.socketTextStream('127.0.0.1', 8080)


# print(dataStream)
# print(dataStream.context())
print("Here!\n")
dataStream.pprint(5)

# split each tweet into words
words = dataStream.flatMap(lambda line: line.split(" "))
print("data!!!\n")
# words.pprint(5)

# filter the words to get only hashtags, then map each hashtag to be a pair of (hashtag,1)
hashtags = words.map(lambda x: (x, 1))

# adding the count of each hashtag to its last count
tags_totals = hashtags.updateStateByKey(aggregate_tags_count)

# do processing for each RDD generated in each interval
tags_totals.foreachRDD(process_rdd)

# start the streaming computation
ssc.start()

# wait for the streaming to finish
ssc.awaitTermination()


# GCP Metric Exporter

## Introduction

### What it does?

This project created to export time series data points from Google Cloud Monitoring and load it into Bigquery table.

### Why do I need it?

The GCP Metric Exporter project created to address the following points:

* Data retention - Following the GCP Monitoring service [retention policy](https://cloud.google.com/monitoring/quotas#data_retention_policy), metrics data will be stored for a limited time, most of the GCP services metrics will retain for 6 weeks, and then will be deleted. 
* Data analysis - Storing metric data in a BigQuery provide a better way to perform a complex analysis of GCP services over time using Standard SQL.

### Architecture

1) Cloud Scheduler - For each metric export we will create new cloud scheduler that contains the required information of the export job the message body and to manage the HTTP trigger.

2) Cloud Function - This function is responsible for executing the export step using the information provided by the cloud scheduler and triggered by HTTP endpoint, and loading the data into the BigQuery.

3) Cloud Storage - The cloud function will make the API call and split the response into different files (using the parameter PAGE_SIZE), and will store it on GCS for the load job into BQ.

4) BigQuery - Store the exported metrics data for future analysis (One table for each metric).


![alt text](images/Metric_Exporter_Architecture.png)

## Prerequisite

In order to run this project we'll need to have:

* [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
* [gsutil](https://cloud.google.com/storage/docs/gsutil_install)
* ```Python >= 3.6```

Please run the following command to install local Python dependencies:

```pip install -r ./local-requirements.txt ```

## Installation

### Authentication
Please authenticate with your user using the gcloud SDK by running the following command:

```gcloud auth login```

For more information please look at [gcloud auth login documentation](https://cloud.google.com/sdk/gcloud/reference/auth/login).

### Configure the Makefile parameters

In order to deploy the pipeline there are configuration parameters on the Makefile that needs to be configured:

- ```PROJECT_ID``` - GCP project id.

- ```CF_REGION``` - GCP region for deploying the Cloud Function.

- ```TIMEOUT``` - Cloud Function timeout (MAX=540).

- ```MEMORY``` - Cloud Function memory in MB (MAX=8192MB).

- ```EXPORT_NAME``` - Keep this name unique for each metric export, this is the scheduler name as well as the table name in BigQuery.

- ```TIME_ZONE``` - Time zone of the Cloud Scheduler.

- ```SCHEDULE``` - [Cron expression](https://cloud.google.com/scheduler/docs/configuring/cron-job-schedules) for triggering the export (Cloud Scheduler).

- ```WEEKS``` - The number of weeks back to get the metric data for each runtime.

- ```DAYS``` - The number of days back to get the metric data for each runtime.

- ```HOURS``` - The number of hours back to get the metric data for each runtime.

- ```FILTER``` - The cloud monitoring [filter expression](https://cloud.google.com/monitoring/api/v3/filters), keep the pattern of single quote (') on the outer part of the filter and double quote (") inside the filter. Example: ```FILTER='metric.type = "storage.googleapis.com/storage/object_count"'```

- ```BQ_DATASET``` - BigQuery dataset name, Configure only at the first deployment.

- ```BQ_LOCATION``` - BigQuery dataset location, Configure only at the first deployment.

- ```PAGE_SIZE``` - The pagination size for splitting the API response by the number of data points.


### Create BigQuery Dataset:

In order to create the BigQuery dataset run the following command:

```make create_bq_dataset```

### Create GCS Bucket

```gsutil mb gs://${PROJECT_ID}-Metric-Exporter```

### Exporting environment variable

Please run the following to export required variables:

```
export PROJECT_ID=<YOUR-PORJECT-ID>
export BUCKET_NAME="${PROJECT_ID}-Metric-Exporter"
```

### Cloud Function service account

The cloud function will preform an API call to GCP Monitoring service and load data into a BigQuery table, for that, we will create a custom role to follow [Least privilege](https://cloud.google.com/iam/docs/using-iam-securely#least_privilege) GCP IAM recommendation.

Please run the following command to create custom role with the monitoring.timeSeries.list permission:
```
gcloud iam roles create metric_exporter_cf_monitoring_api_role --project=${PROJECT_ID} \
  --title=metric_exporter_cf_monitoring_api_role --description="Role for Monitoring API timeSeries.list" \
  --permissions=monitoring.timeSeries.list --stage=GA
```

Create the Cloud Function service account:

```
gcloud iam service-accounts create metric-exporter-cf-sa \
    --description="Cloud Function metric exporter service account" \
    --display-name="Cloud Functio metric exporter service account"
```
### Grant permissions

Monitoring API:
```
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:metric-exporter-cf-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="projects/${PROJECT_ID}/roles/metric_exporter_cf_monitoring_api_role"
```

BigQuery:

```
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:metric-exporter-cf-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/bigquery.user"
```

GCS:

```
gsutil iam ch serviceAccount:metric-exporter-cf-sa@${PROJECT_ID}.iam.gserviceaccount.com:legacyBucketWriter gs://${BUCKET_NAME}
```


The last permission for the Cloud Function service account is the Data Editor on the Dataset level, please follow the bellow steps (irrelevant information blacked):

Please copy the cloud function service account name, you can get it by running the following command:

```make get_cf_sa_name```

On the GCP console please navigate to Bigquery:

![alt text](images/BQ_nav.png)

On the BigQuery UI, under your BigQuery project, click on expend node:

![alt text](images/BQ_project_expend.png)

On this page you can see your datasets that you created on previews step under your project. Click on the tree dots to the right of the dataset name, and them click on "Open":

![alt text](images/BQ_open_dataset.png)

On the next page, please click on "SHARE DATASET":

![alt text](images/BQ_share_dataset.png)

On the new page, please enter the service account name (in blue), and for the role, please click on "Select a role" and chose BigQuery > BigQuery Data Editor: 

![alt text](images/BQ_dataset_permissions.png)

Now please click on "ADD" and on "Done".

For more information please look at [granting access to a dataset](https://cloud.google.com/bigquery/docs/dataset-access-controls#granting_access_to_a_dataset).

### Cloud Scheduler Service account 
Create the Cloud Scheduler service account:

```
gcloud iam service-accounts create metric-exporter-scheduler-sa \
    --description="Cloud Scheduler metric exporter service account" \
    --display-name="Cloud Scheduler metric exporter service account"
```

Grant to the scheduler service account the "Cloud function invoker" role:

```
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:metric-exporter-scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/cloudfunctions.invoker"
```

## Deploy
<b> Please make sure that all the parameter in the makefile are correct before running the following.</b>

Now we are all set for deploy.

In order to deploy the Cloud Function and Schedule the first export please run the command:

```make full_deploy```

When you get the following question:

```Allow unauthenticated invocations of new function [metric_exporter]?```

Please type "N" in order to prevent any unauthenticated invocation.

In case that you already have a Cloud Function, and you want to deploy on new export, please run the following command to deploy new cloud scheduler:

```make schedule_metric_export```

## Clean

To delete the Cloud Function please run:

``` make delete_cloud_function ```

To specific export please run:

``` delete_scheduler ```

Any comments or suggestions are welcome.
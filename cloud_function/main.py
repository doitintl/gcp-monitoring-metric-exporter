import logging
from google.cloud import monitoring_v3
from google.cloud import bigquery
from datetime import timedelta
from datetime import datetime
import time
import os
import json
from google.cloud.storage import Blob
from google.cloud import storage

monitoring_client = monitoring_v3.MetricServiceClient()
bq_client = bigquery.Client()
storage_client = storage.Client()

export_datetime = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def get_interval(weeks_ago, days_ago, hours_ago, seconds_ago=0):
    time_now = time.time()
    start_time = get_second_delta(weeks_ago, days_ago, hours_ago, seconds_ago)
    seconds = int(time_now)
    nanos = int((time_now - seconds) * 10 ** 9)

    interval = monitoring_v3.TimeInterval(
        {
            "end_time": {"seconds": seconds, "nanos": nanos},
            "start_time": {"seconds": (seconds - int(start_time)), "nanos": nanos},
        }
    )

    return interval


def get_request_body(project_id, metric_filter, interval, page_size, full_view=True):
    project_name = f"projects/{project_id}"

    if full_view:
        view = monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
    else:
        view = monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.HEADERS

    request = {
        "name": project_name,
        "filter": metric_filter,
        "interval": interval,
        "aggregation": None,
        "view": view,
        "page_size": page_size,
    }
    return request


def get_metric_data(request):
    logging.debug("Sending API request to the monitoring backend")

    results = monitoring_client.list_time_series(request)

    logging.debug("Got response from the server")

    return results


def get_second_delta(weeks, days, hours, seconds):
    return timedelta(weeks=weeks, days=days, hours=hours, seconds=seconds).total_seconds()


def parse_as_json_new_line(data):
    logging.debug("Parsing data into data points")
    points = []
    for page in data:

        metric_name = page.metric
        resource_name = page.resource

        for point in page.points:

            dict_point = {
                'time': point.interval.start_time.strftime('%d/%m/%Y %H:%M:%S'),
                'metric_type': metric_name.type,
                'resource_type': resource_name.type,
                'int_value': point.value.int64_value,
                'double_value': point.value.double_value,
                'string_value': point.value.string_value,
                'bool_value': point.value.bool_value
            }

            for key, value in metric_name.labels.items():
                dict_point[key] = value

            for key, value in resource_name.labels.items():
                dict_point[key] = value

            points.append(dict_point)

    logging.debug("Parsing completed")

    return points


def load_to_bq(project_id, dataset, table_name, gcs_path):
    logging.info(f"BigQuery load destination: {project_id}:{dataset}.{table_name}")

    table_id = f"{project_id}.{dataset}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON, autodetect=True,
    )

    job = bq_client.load_table_from_uri(f'{gcs_path}', table_id, job_config=job_config)

    job.result()  # Waits for the job to complete.

    table = bq_client.get_table(table_id)  # Make an API request.
    logging.info(
        "Load job completed, total rows number is {} and with {} columns on {}".format(
            table.num_rows, len(table.schema), table_id
        )
    )


def write_to_local_disk(file_prefix, page_number, page_data):
    page_local_path = f'/tmp/{file_prefix}_{page_number}.jsonl'
    logging.debug(f"Writing data point into local path {page_local_path}")
    with open(page_local_path, 'w') as out_file:
        for data_point in page_data:
            out_file.write(json.dumps(data_point))
            out_file.write("\n")

    logging.debug(f"Writing tmp file {page_local_path} completed with no errors")

    return page_local_path


def delete_local_file(path):
    logging.debug(f'Removing tmp local file {path}')
    os.remove(path)
    logging.debug(f'Local file {path} successfully removed')


def write_to_gcs(bucket_name, file_prefix, page_number, page_data):
    local_page_path = write_to_local_disk(file_prefix, page_number, page_data)
    bucket_path = storage_client.get_bucket(bucket_name)
    gcs_file_path = f'{file_prefix}/{export_datetime}/{page_number}.jsonl'

    logging.debug(f'Uploading local file {local_page_path} to gcs path {gcs_file_path}')

    blob = Blob(gcs_file_path, bucket_path)
    blob.upload_from_filename(local_page_path)

    logging.debug(f'Uploading {local_page_path} to gcs path {gcs_file_path} successfully done')

    delete_local_file(local_page_path)


def get_parsed_request(request):
    logging.debug(f'Request content:{request}')

    int_key_names = ['weeks',
                     'days',
                     'hours',
                     'page_size']

    parsed_request = request.get_json()

    for name in int_key_names:
        parsed_request[name] = int(parsed_request[name])

    return parsed_request


def export(request):
    parsed_request = get_parsed_request(request)

    interval = get_interval(parsed_request['weeks'],
                            parsed_request['days'],
                            parsed_request['hours'])

    api_request = get_request_body(parsed_request['project_id'],
                                   parsed_request['filter'],
                                   interval,
                                   parsed_request['page_size'])

    raw_metrics_data = get_metric_data(api_request)

    page_num = 1
    parsed_page = parse_as_json_new_line(raw_metrics_data.time_series)
    write_to_gcs(parsed_request['bucket_name'],
                 parsed_request['bq_destination_table'],
                 page_num,
                 parsed_page)

    while raw_metrics_data.next_page_token:
        api_request.update({
            'page_token': raw_metrics_data.next_page_token
        })
        raw_metrics_data = get_metric_data(api_request)

        page_num += 1

        parsed_page = parse_as_json_new_line(raw_metrics_data.time_series)
        write_to_gcs(parsed_request['bucket_name'],
                     parsed_request['bq_destination_table'],
                     page_num,
                     parsed_page)

    gcs_path = f"gs://{parsed_request['bucket_name']}/{parsed_request['bq_destination_table']}/{export_datetime}/*"
    
    load_to_bq(parsed_request['project_id'],
               parsed_request['bq_destination_dataset'],
               parsed_request['bq_destination_table'],
               gcs_path)
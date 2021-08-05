import json
import os
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument("--project", required=True)

    parser.add_argument("--filter", required=True)

    parser.add_argument("--weeks",
                        required=True, type=int)

    parser.add_argument("--days",
                        required=True, type=int)

    parser.add_argument("--hours",
                        required=True, type=int)

    parser.add_argument("--MSG_TMP_DIR", required=True)

    parser.add_argument("--MSG_BODY_FILE_NAME", required=True)

    parser.add_argument("--bq_destination_dataset", required=True)

    parser.add_argument("--bq_destination_table", required=True)

    parser.add_argument("--BUCKET_NAME", required=True)

    parser.add_argument("--PAGE_SIZE", required=True, type=int)

    args = parser.parse_args()

    msg = {"project_id": args.project,
           "filter": args.filter,
           "weeks": args.weeks,
           "days": args.days,
           "hours": args.hours,
           "bq_destination_dataset": args.bq_destination_dataset,
           "bq_destination_table": args.bq_destination_table,
           "page_size": args.PAGE_SIZE,
           "bucket_name": args.BUCKET_NAME}

    if not os.path.exists(args.MSG_TMP_DIR):
        os.makedirs(f"{args.MSG_TMP_DIR}/")

    with open(f"{args.MSG_TMP_DIR}/{args.MSG_BODY_FILE_NAME}", "w") as fp:
        json.dump(msg, fp)

from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta

app = Flask(__name__)

# MongoDB connection
client = MongoClient("mongodb://your_mongo_uri")
db = client['your_db_name']
collection = db['your_collection_name']

# Function to fetch report data based on dynamic criteria
def fetch_report(filters):
    # Build the filter condition based on user input
    filter_condition = {
        "migrationHistory.migratedBy": {"$ne": "cdlmdbmp"},
        "bankDocument.tenants": {"$elemMatch": {"domain": filters.get("domain"), "division": filters.get("division")}},
        "systemCreatedDateTime": {
            "$gte": datetime.strptime(filters["startDate"], "%Y-%m-%dT%H:%M:%S"),
            "$lte": datetime.strptime(filters["endDate"], "%Y-%m-%dT%H:%M:%S")
        }
    }
    # Optionally include SubDivision filter if provided
    if filters.get("subdivision"):
        filter_condition["subdivision"] = filters["subdivision"]

    # Additional grouping option: security group or origination system
    group_by_field = filters.get("groupBy", "adminDocument.originationSystemName")
    # Determine time bucket unit and bin size based on chosen interval
    time_interval = int(filters.get("timeInterval", 1))  # in hours
    report_type = "hour"  # Default aggregation by hour if not cumulative/daily
    if filters.get("timeGrouping") == "daily":
        report_type = "day"

    pipeline = [
        {"$match": filter_condition},
        {
            "$group": {
                "_id": {
                    "group": f"${group_by_field}",
                    "timeBucket": {
                        "$dateTrunc": {
                            "date": "$systemCreatedDateTime",
                            "unit": report_type,
                            "binSize": time_interval
                        }
                    }
                },
                "count": {"$sum": 1}
            }
        },
        {
            "$group": {
                "_id": "$_id.group",
                "buckets": {"$push": {"timeBucket": "$_id.timeBucket", "count": "$count"}},
                "totalCount": {"$sum": "$count"}
            }
        },
        {"$sort": {"_id": 1}}
    ]
    results = list(collection.aggregate(pipeline))
    return results

@app.route('/')
def index():
    # Default start and end dates: start = 16 Nov 2024, end = today (for demo, we use two days ago to now)
    today = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    default_start_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
    return render_template('index.html', default_start_date=default_start_date, default_end_date=today)

@app.route('/api/report', methods=['POST'])
def get_report():
    filters = request.json
    report = fetch_report(filters)
    return jsonify(report)

if __name__ == "__main__":
    app.run(debug=True)

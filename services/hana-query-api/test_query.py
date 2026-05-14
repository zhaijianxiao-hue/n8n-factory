import json, urllib.request

sql = 'SELECT a."MATNR",t."MAKTX",a."MTART",a."MATKL",a."MEINS" FROM SAPHANADB."MARA" a INNER JOIN SAPHANADB."MAKT" t ON a."MATNR" = t."MATNR" AND t."SPRAS" = \'1\' WHERE a.mandt = \'800\' LIMIT 10'

data = json.dumps({"sql": sql}).encode()
req = urllib.request.Request(
    "http://localhost:8766/query",
    data=data,
    headers={"Content-Type": "application/json"},
)
try:
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read().decode())
    print(f"Total: {result['total']}")
    print(f"Columns: {result['columns']}")
    for row in result["data"][:3]:
        print(row)
except urllib.error.HTTPError as e:
    print(f"Error {e.code}: {e.read().decode()}")

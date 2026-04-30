import csv
from rdflib import Graph, URIRef, Literal, XSD
from rdflib.namespace import RDF

g = Graph()
ns = "http://example.org/turing#"

with open("triples.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        s = URIRef(ns + row["subject"].replace(" ", "_"))
        p = URIRef(ns + row["predicate"])
        o = row["object"]
        # 简单判断：如果是日期，加 xsd:date 类型
        if "-" in o and len(o) == 10:
            o = Literal(o, datatype=XSD.date)
        else:
            o = Literal(o)
        g.add((s, p, o))

g.serialize(destination="turing.ttl", format="turtle")
print("turing.ttl 已更新")

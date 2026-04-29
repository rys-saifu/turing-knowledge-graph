import spacy
import pandas as pd
from pathlib import Path

nlp = spacy.load("en_core_web_sm")

def extract_triples_enhanced(text):
    doc = nlp(text)
    triples = []
    
    # 定义关系触发词及其对应的关系名、期望的实体类型
    relation_triggers = {
        "bornIn":   {"verbs": ["born"], "dep": "prep", "obj_type": "GPE"},
        "proposed": {"verbs": ["propose", "introduce"], "dep": "dobj", "obj_type": ""},
        "participatedIn": {"verbs": ["work", "serve"], "dep": "prep", "obj_type": "ORG"},
        "wrote":    {"verbs": ["write"], "dep": "dobj", "obj_type": ""},
        "awarded":  {"verbs": ["appoint", "award"], "dep": "pobj", "obj_type": ""},
        "diedIn":   {"verbs": ["die"], "dep": "prep", "obj_type": "GPE"}
    }
    
    for sent in doc.sents:
        # 获取句子中的所有实体
        entities = [(ent.text, ent.label_) for ent in sent.ents]
        # 对于每个动词，检查是否为触发词
        for token in sent:
            if token.pos_ == "VERB" and token.lemma_ in [v for trig in relation_triggers.values() for v in trig["verbs"]]:
                # 找到对应的关系
                rel = None
                for r, info in relation_triggers.items():
                    if token.lemma_ in info["verbs"]:
                        rel = r
                        break
                if not rel:
                    continue
                # 寻找主语（头实体）
                subj = None
                for child in token.children:
                    if child.dep_ in ("nsubj", "nsubjpass"):
                        subj = child.text
                        break
                if not subj:
                    # 尝试从实体中寻找人名作为默认主语
                    for ent_text, ent_type in entities:
                        if ent_type == "PERSON":
                            subj = ent_text
                            break
                # 寻找宾语（尾实体）
                obj = None
                info = relation_triggers[rel]
                if info["dep"] == "dobj":
                    for child in token.children:
                        if child.dep_ == "dobj":
                            obj = child.text
                            break
                elif info["dep"] == "prep":
                    for child in token.children:
                        if child.dep_ == "prep":
                            for grand in child.children:
                                if grand.dep_ == "pobj":
                                    obj = grand.text
                                    break
                elif info["dep"] == "pobj":
                    for child in token.children:
                        if child.dep_ == "pobj":
                            obj = child.text
                            break
                # 如果没有找到宾语，尝试从实体中找符合类型的
                if not obj and info["obj_type"]:
                    for ent_text, ent_type in entities:
                        if ent_type == info["obj_type"]:
                            obj = ent_text
                            break
                if subj and obj:
                    triples.append((subj, rel, obj))
    # 去重
    triples = list(set(triples))
    return triples

if __name__ == "__main__":
    text_path = Path("turing_text.txt")
    if not text_path.exists():
        print("请创建 turing_text.txt 文件并放入关于图灵的英文文本")
    else:
        text = text_path.read_text(encoding="utf-8")
        triples = extract_triples_enhanced(text)
        df = pd.DataFrame(triples, columns=["subject", "predicate", "object"])
        print("抽取到的三元组：")
        print(df)
        df.to_csv("extracted_triples.csv", index=False)
        # 合并到原 triples.csv
        original = Path("triples.csv")
        if original.exists():
            old_df = pd.read_csv(original)
            combined = pd.concat([old_df, df]).drop_duplicates()
            combined.to_csv(original, index=False)
            print(f"合并后总三元组数：{len(combined)}")
        else:
            print("未找到原 triples.csv，仅生成 extracted_triples.csv")

import spacy
import pandas as pd
import re
from pathlib import Path

# 加载 spaCy 英文模型（确保已安装 en_core_web_sm）
nlp = spacy.load("en_core_web_sm")

# ----------------------------- 实体消歧词典 -----------------------------
# 定义别名字典：{标准实体名称: [别名列表]}
ALIAS_MAP = {
    "Alan Turing": ["Alan Turing", "Turing", "He", "he", "him"],
    "London": ["London"],
    "Wilmslow": ["Wilmslow", "Cheshire"],
    "Turing machine": ["Turing machine", "machine", "the Turing machine", "universal machine"],
    "Turing test": ["Turing test", "test", "the Turing test"],
    "Bletchley Park": ["Bletchley Park", "the Park", "Park"],
    "On Computable Numbers": ["On Computable Numbers", "the paper", "paper", "his paper"],
    "Computing Machinery and Intelligence": ["Computing Machinery and Intelligence", "his 1950 paper"],
    "Officer of the Order of the British Empire": ["Officer of the Order of the British Empire", "OBE", "Officer"],
    "World War II": ["World War II", "the war", "WWII"],
}

# 构建反向映射（别名 → 标准名）
alias_to_std = {}
for std, aliases in ALIAS_MAP.items():
    for alias in aliases:
        alias_to_std[alias.lower()] = std

def disambiguate_entity(mention: str, context_sentence: str = "") -> str:
    """
    将实体指称项 mention 消歧到标准实体名称。
    优先使用词典映射，若不在词典中则返回原字符串。
    """
    mention_lower = mention.lower().strip()
    # 直接匹配别名
    if mention_lower in alias_to_std:
        return alias_to_std[mention_lower]
    # 处理可能的标点或多余空格
    cleaned = re.sub(r'[^\w\s]', '', mention_lower)
    if cleaned in alias_to_std:
        return alias_to_std[cleaned]
    # 对于数字（如年份）保留原样
    if mention.isdigit() or (mention.startswith('"') and mention.endswith('"')):
        return mention
    # 否则原样返回（可以后续手动审查）
    return mention

def resolve_coreference(doc):
    """
    简单的代词消解：将每个句子中的 "He"、"his" 等替换为最近的人名。
    此实现基于前一句的主语实体（Alan Turing）。
    """
    resolved_text = []
    last_person = None
    for sent in doc.sents:
        sent_text = sent.text
        # 查找本句中的人名
        persons = [ent.text for ent in sent.ents if ent.label_ == "PERSON"]
        if persons:
            last_person = persons[0]  # 取第一个人名
        # 如果存在代词 "He", "he", "His", "his" 且知道 last_person
        if last_person and re.search(r'\b(He|he|His|his)\b', sent_text):
            sent_text = re.sub(r'\b(He|he)\b', last_person, sent_text)
            sent_text = re.sub(r'\b(His|his)\b', last_person + "'s", sent_text)
        resolved_text.append(sent_text)
    return " ".join(resolved_text)

def extract_triples_with_disambiguation(text):
    # 先进行代词消解
    doc = nlp(text)
    resolved_text = resolve_coreference(doc)
    # 重新解析消解后的文本
    doc_resolved = nlp(resolved_text)
    
    # 关系触发词配置（与原脚本相同）
    relation_triggers = {
        "bornIn":   {"verbs": ["born"], "dep": "prep", "obj_type": "GPE"},
        "proposed": {"verbs": ["propose", "introduce"], "dep": "dobj", "obj_type": ""},
        "participatedIn": {"verbs": ["work", "serve"], "dep": "prep", "obj_type": "ORG"},
        "wrote":    {"verbs": ["write"], "dep": "dobj", "obj_type": ""},
        "awarded":  {"verbs": ["appoint", "award"], "dep": "pobj", "obj_type": ""},
        "diedIn":   {"verbs": ["die"], "dep": "prep", "obj_type": "GPE"}
    }
    
    triples = []
    for sent in doc_resolved.sents:
        entities = [(ent.text, ent.label_) for ent in sent.ents]
        for token in sent:
            if token.pos_ == "VERB" and token.lemma_ in [v for trig in relation_triggers.values() for v in trig["verbs"]]:
                # 找到对应关系名
                rel = None
                for r, info in relation_triggers.items():
                    if token.lemma_ in info["verbs"]:
                        rel = r
                        break
                if not rel:
                    continue
                # 寻找主语
                subj = None
                for child in token.children:
                    if child.dep_ in ("nsubj", "nsubjpass"):
                        subj = child.text
                        break
                if not subj:
                    for ent_text, ent_type in entities:
                        if ent_type == "PERSON":
                            subj = ent_text
                            break
                # 寻找宾语
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
                if not obj and info["obj_type"]:
                    for ent_text, ent_type in entities:
                        if ent_type == info["obj_type"]:
                            obj = ent_text
                            break
                if subj and obj:
                    # 实体消歧
                    subj_std = disambiguate_entity(subj, sent.text)
                    obj_std = disambiguate_entity(obj, sent.text)
                    triples.append((subj_std, rel, obj_std))
    # 去重
    triples = list(set(triples))
    return triples

if __name__ == "__main__":
    text_path = Path("turing_text.txt")
    if not text_path.exists():
        print("请创建 turing_text.txt 文件并放入关于图灵的英文文本")
    else:
        text = text_path.read_text(encoding="utf-8")
        triples = extract_triples_with_disambiguation(text)
        df = pd.DataFrame(triples, columns=["subject", "predicate", "object"])
        print("抽取并消歧后的三元组：")
        print(df)
        df.to_csv("extracted_triples_disambiguated.csv", index=False)
        # 合并到主文件
        original = Path("triples.csv")
        if original.exists():
            old_df = pd.read_csv(original)
            combined = pd.concat([old_df, df]).drop_duplicates()
            combined.to_csv(original, index=False)
            print(f"合并后总三元组数：{len(combined)}")
        else:
            print("未找到原 triples.csv，仅生成 extracted_triples_disambiguated.csv")

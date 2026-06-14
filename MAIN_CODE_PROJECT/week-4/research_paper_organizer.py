# Research Paper Organizer with Citation Tracking
from datetime import date
papers    = {}
citations = {}
_pid = 1
TOPICS = ["Machine Learning","Deep Learning","NLP","Computer Vision","Robotics",
          "Cybersecurity","Databases","Networks","Algorithms","HCI","Bioinformatics"]
def add_paper(title, authors, year, journal, topic, doi=None, abstract=None):
    global _pid
    if topic not in TOPICS:
        print(f"  Unknown topic. Options: {TOPICS}"); return None
    pid = f"PAP{_pid:04d}"; _pid += 1
    papers[pid] = {
        "title":title, "authors":authors, "year":year,
        "journal":journal, "topic":topic, "doi":doi or "N/A",
        "abstract":abstract or "", "citation_count":0,
        "cited_by":[], "references":[]
    }
    citations[pid] = []
    print(f"  [{pid}] {title[:50]} | {', '.join(authors[:2])} et al. | {year} | {topic}")
    return pid
def add_citation(from_pid, to_pid):
    if from_pid not in papers or to_pid not in papers:
        print("  One or both paper IDs not found."); return False
    if to_pid in papers[from_pid]["references"]:
        print(f"  [{from_pid}] already cites [{to_pid}]."); return False
    papers[from_pid]["references"].append(to_pid)
    papers[to_pid]["citation_count"] += 1
    papers[to_pid]["cited_by"].append(from_pid)
    citations[to_pid].append(from_pid)
    print(f"  [{from_pid}] → cites → [{to_pid}] | [{to_pid}] now has {papers[to_pid]['citation_count']} citation(s)")
    return True
def search_by_topic(topic):
    results = [(pid, p) for pid, p in papers.items() if p["topic"].lower() == topic.lower()]
    print(f"\n  [{topic}] — {len(results)} paper(s):")
    for pid, p in sorted(results, key=lambda x: -x[1]["year"]):
        print(f"  {pid} | {p['year']} | {p['title'][:45]:<45} | Cited: {p['citation_count']}")
def search_by_author(author_name):
    kw = author_name.lower()
    results = [(pid, p) for pid, p in papers.items()
               if any(kw in a.lower() for a in p["authors"])]
    print(f"\n  Author search '{author_name}': {len(results)} result(s)")
    for pid, p in results:
        print(f"  {pid} | {p['year']} | {p['title'][:45]}")
def paper_detail(pid):
    if pid not in papers: print("  Not found."); return
    p = papers[pid]
    print(f"\n{'='*52}")
    print(f"  [{pid}] {p['title']}")
    print(f"  Authors  : {', '.join(p['authors'])}")
    print(f"  Year     : {p['year']}  |  Journal: {p['journal']}")
    print(f"  Topic    : {p['topic']}  |  DOI: {p['doi']}")
    print(f"  Citations: {p['citation_count']}")
    if p["abstract"]:
        print(f"  Abstract : {p['abstract'][:120]}...")
    if p["cited_by"]:
        print(f"  Cited by : {', '.join(p['cited_by'])}")
    if p["references"]:
        print(f"  References: {', '.join(p['references'])}")
    print(f"{'='*52}")

def top_cited(n=5):
    ranked = sorted(papers.items(), key=lambda x: -x[1]["citation_count"])[:n]
    print(f"\n  Top {n} Most Cited Papers:")
    for rank, (pid, p) in enumerate(ranked, 1):
        print(f"  {rank}. [{pid}] {p['title'][:45]:<45} | {p['citation_count']} citations | {p['year']}")

def generate_bibliography(pids, style="APA"):
    print(f"\n  Bibliography ({style} style):")
    for pid in pids:
        if pid not in papers: continue
        p = papers[pid]
        authors_str = ", ".join(p["authors"])
        if style == "APA":
            print(f"  {authors_str} ({p['year']}). {p['title']}. {p['journal']}. {p['doi']}")
        elif style == "MLA":
            print(f'  {authors_str}. "{p["title"]}." {p["journal"]}, {p["year"]}.')

def catalog_report():
    print(f"\n{'='*52}\n  RESEARCH PAPER CATALOG REPORT\n{'='*52}")
    topic_counts = {}
    for p in papers.values():
        topic_counts[p["topic"]] = topic_counts.get(p["topic"], 0) + 1
    total_cites = sum(p["citation_count"] for p in papers.values())
    avg_cites   = round(total_cites / len(papers), 2) if papers else 0
    years = [p["year"] for p in papers.values()]
    print(f"  Total Papers   : {len(papers)}")
    print(f"  Total Citations: {total_cites}  |  Avg: {avg_cites}")
    print(f"  Year Range     : {min(years)} – {max(years)}" if years else "")
    print(f"\n  By Topic:")
    for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
        print(f"    {topic:<22}: {count}")
    print(f"{'='*52}")

def main():
    print("=== Research Paper Organizer ===")
    p1 = add_paper("Attention Is All You Need",
                   ["Vaswani, A.","Shazeer, N.","Parmar, N."], 2017,
                   "NeurIPS", "Deep Learning", "10.48550/arxiv.1706.03762",
                   "Introducing the Transformer architecture based entirely on attention mechanisms.")
    p2 = add_paper("BERT: Pre-training of Deep Bidirectional Transformers",
                   ["Devlin, J.","Chang, M.","Lee, K."], 2019,
                   "NAACL", "NLP", "10.18653/v1/N19-1423",
                   "Language model pre-training using bidirectional transformer encoder.")
    p3 = add_paper("ImageNet Classification with Deep CNNs",
                   ["Krizhevsky, A.","Sutskever, I.","Hinton, G."], 2012,
                   "NeurIPS", "Computer Vision", "10.1145/3065386",
                   "AlexNet winning ImageNet with deep convolutional networks.")
    p4 = add_paper("Generative Adversarial Nets",
                   ["Goodfellow, I.","Pouget-Abadie, J."], 2014,
                   "NeurIPS", "Deep Learning", "10.48550/arxiv.1406.2661")
    p5 = add_paper("GPT-3: Language Models are Few-Shot Learners",
                   ["Brown, T.","Mann, B.","Ryder, N."], 2020,
                   "NeurIPS", "NLP", "10.48550/arxiv.2005.14165")
    p6 = add_paper("Deep Residual Learning for Image Recognition",
                   ["He, K.","Zhang, X.","Ren, S."], 2016,
                   "CVPR", "Computer Vision", "10.1109/CVPR.2016.90")
    add_citation(p2, p1); add_citation(p5, p1); add_citation(p5, p2)
    add_citation(p4, p3); add_citation(p6, p3); add_citation(p2, p6)
    search_by_topic("NLP")
    search_by_author("Vaswani")
    top_cited(4)
    paper_detail(p1)
    generate_bibliography([p1, p2, p3], style="APA")
    catalog_report()

if __name__ == "__main__":
    main()

"""
評価シート分析スクリプト

evaluation_sheet.csv に記入された評価スコアを読み込み、
ハイパーパラメータとの関係を分析する。

使い方:
  python3 analyze_evaluation.py
"""

import csv
import statistics

EVAL_FILE = "/home/junkanki/naka/evaluation_sheet.csv"

SCORE_COLUMNS = [
    "medical_knowledge_1", "medical_knowledge_2", "medical_knowledge_3",
    "guideline_1", "guideline_2", "guideline_3",
    "clinical_1", "clinical_2",
    "coherence_1", "coherence_2",
    "suggest_1", "suggest_2",
]

CATEGORY_MAP = {
    "医学基礎知識": ["medical_knowledge_1", "medical_knowledge_2", "medical_knowledge_3"],
    "ガイドライン": ["guideline_1", "guideline_2", "guideline_3"],
    "カルテ調理解": ["clinical_1", "clinical_2"],
    "まとまり":     ["coherence_1", "coherence_2"],
    "カルテsuggest": ["suggest_1", "suggest_2"],
}


def load_data():
    rows = []
    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # スコアを数値に変換
            scores = {}
            for col in SCORE_COLUMNS:
                val = row.get(col, "").strip()
                scores[col] = float(val) if val else None
            row["_scores"] = scores
            rows.append(row)
    return rows


def compute_stats(rows):
    """各モデルのカテゴリ別平均と総合スコアを計算"""
    results = []
    for row in rows:
        scores = row["_scores"]
        all_scores = [v for v in scores.values() if v is not None]
        if not all_scores:
            continue

        cat_avgs = {}
        for cat_name, cols in CATEGORY_MAP.items():
            vals = [scores[c] for c in cols if scores[c] is not None]
            cat_avgs[cat_name] = statistics.mean(vals) if vals else None

        results.append({
            "model": row["model"],
            "loss": row["loss"],
            "lora_r": row["lora_r"],
            "lora_alpha": row["lora_alpha"],
            "lr": row["lr"],
            "epochs": row["epochs"],
            "total_avg": statistics.mean(all_scores),
            **cat_avgs,
        })
    return results


def analyze_hyperparams(results):
    """ハイパーパラメータごとの傾向を分析"""
    print("\n" + "=" * 70)
    print("ハイパーパラメータ別 分析")
    print("=" * 70)

    # base を除外
    trained = [r for r in results if r["model"] != "base"]
    if not trained:
        print("評価データがありません")
        return

    # LoRA r 別
    print("\n--- LoRA rank (r) 別 平均スコア ---")
    r_groups = {}
    for r in trained:
        key = r["lora_r"]
        r_groups.setdefault(key, []).append(r["total_avg"])
    for k in sorted(r_groups.keys()):
        avg = statistics.mean(r_groups[k])
        print(f"  r={k:>4s}: avg={avg:.2f} (n={len(r_groups[k])})")

    # 学習率別
    print("\n--- 学習率 (lr) 別 平均スコア ---")
    lr_groups = {}
    for r in trained:
        key = r["lr"]
        lr_groups.setdefault(key, []).append(r["total_avg"])
    for k in sorted(lr_groups.keys()):
        avg = statistics.mean(lr_groups[k])
        print(f"  lr={k:>6s}: avg={avg:.2f} (n={len(lr_groups[k])})")

    # エポック別
    print("\n--- エポック数別 平均スコア ---")
    ep_groups = {}
    for r in trained:
        key = r["epochs"]
        ep_groups.setdefault(key, []).append(r["total_avg"])
    for k in sorted(ep_groups.keys()):
        avg = statistics.mean(ep_groups[k])
        print(f"  epochs={k:>2s}: avg={avg:.2f} (n={len(ep_groups[k])})")

    # alpha/r 比率別
    print("\n--- alpha/r 比率別 平均スコア ---")
    ratio_groups = {}
    for r in trained:
        try:
            ratio = int(r["lora_alpha"]) / int(r["lora_r"])
            key = f"{ratio:.1f}"
        except (ValueError, ZeroDivisionError):
            continue
        ratio_groups.setdefault(key, []).append(r["total_avg"])
    for k in sorted(ratio_groups.keys(), key=float):
        avg = statistics.mean(ratio_groups[k])
        print(f"  alpha/r={k:>4s}: avg={avg:.2f} (n={len(ratio_groups[k])})")

    # Loss vs 人間評価の相関
    print("\n--- Loss vs 人間評価スコア ---")
    pairs = []
    for r in trained:
        try:
            pairs.append((float(r["loss"]), r["total_avg"]))
        except (ValueError, TypeError):
            continue
    if len(pairs) >= 3:
        losses, scores = zip(*pairs)
        # 簡易相関（スピアマン的に順位で見る）
        loss_rank = sorted(range(len(losses)), key=lambda i: losses[i])
        score_rank = sorted(range(len(scores)), key=lambda i: -scores[i])
        print(f"  Loss低い順 Top5: {[trained[i]['model'] for i in loss_rank[:5]]}")
        print(f"  人間評価 Top5:   {[trained[i]['model'] for i in score_rank[:5]]}")

        # lossと人間評価の一致度
        loss_top5 = set(loss_rank[:5])
        score_top5 = set(score_rank[:5])
        overlap = len(loss_top5 & score_top5)
        print(f"  Top5 の一致数: {overlap}/5")
        if overlap <= 2:
            print("  → Lossと人間評価の相関は弱い。Lossだけでモデル選定すべきでない。")
        elif overlap >= 4:
            print("  → Lossと人間評価はよく一致。Loss指標は信頼できる。")
        else:
            print("  → 部分的に一致。Lossは参考になるが、人間評価も重要。")

    # カテゴリ別の得意・不得意
    print("\n--- カテゴリ別 ベストモデル ---")
    for cat_name in CATEGORY_MAP:
        best = max(trained, key=lambda r: r.get(cat_name) or 0)
        score = best.get(cat_name)
        if score:
            print(f"  {cat_name}: {best['model']} (avg={score:.2f})")


def main():
    rows = load_data()
    results = compute_stats(rows)

    if not results:
        print("evaluation_sheet.csv にスコアが記入されていません。")
        print("各セルに 1〜5 のスコアを入力してから再実行してください。")
        return

    # ランキング表示
    print("=" * 70)
    print("モデル評価ランキング（総合スコア順）")
    print("=" * 70)
    results.sort(key=lambda r: r["total_avg"], reverse=True)
    print(f"{'順位':>4s}  {'モデル':30s}  {'Loss':>7s}  {'総合':>5s}  {'基礎知識':>8s}  {'GL':>5s}  {'カルテ':>6s}  {'まとまり':>8s}")
    print("-" * 90)
    for i, r in enumerate(results, 1):
        cats = [r.get(c) for c in CATEGORY_MAP]
        cat_strs = [f"{v:.1f}" if v else "N/A" for v in cats]
        print(f"{i:>4d}  {r['model']:30s}  {r['loss']:>7s}  {r['total_avg']:5.2f}  {'  '.join(cat_strs)}")

    analyze_hyperparams(results)

    print("\n" + "=" * 70)
    print("示唆・考察")
    print("=" * 70)
    if results:
        best = results[0]
        print(f"  総合ベスト: {best['model']} (avg={best['total_avg']:.2f}, loss={best['loss']})")
        print(f"  設定: r={best['lora_r']}, alpha={best['lora_alpha']}, lr={best['lr']}, epochs={best['epochs']}")


if __name__ == "__main__":
    main()

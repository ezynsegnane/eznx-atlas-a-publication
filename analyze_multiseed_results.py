# ============================================================================
# analyze_multiseed_results.py - Analyse statistique des résultats multi-graines
# ============================================================================
# Calcule: moyenne ± écart-type, IC 95% (bootstrap), tests Wilcoxon
# Génère: tableaux LaTeX et Markdown pour l'article
# ============================================================================

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict
import warnings

import numpy as np
from scipy import stats


# ============================================================================
# CONFIGURATION
# ============================================================================

VARIANTS = ["none", "demo", "demo+anthro"]
VARIANT_LABELS = {
    "none": "ECG seul",
    "demo": "ECG + demo",
    "demo+anthro": "ECG + complet"
}
DS5_LABELS = ["NORM", "MI", "STTC", "CD", "HYP"]

# Nombre d'itérations bootstrap
N_BOOTSTRAP = 10000
CONFIDENCE_LEVEL = 0.95


# ============================================================================
# CHARGEMENT DES DONNÉES
# ============================================================================

def load_all_results(runs_dir: Path) -> Dict[str, Dict[int, Dict]]:
    """
    Charge tous les fichiers de résultats JSON.
    
    Returns:
        Dict[variant][seed] = results_dict
    """
    results = defaultdict(dict)
    
    for variant in VARIANTS:
        pattern = f"ATLAS_A_v5_{variant}_seed*"
        for run_dir in runs_dir.glob(pattern):
            # Extraire le seed du nom du répertoire
            try:
                seed = int(run_dir.name.split("_seed")[-1])
            except:
                continue
            
            # Chercher le fichier de résultats
            results_file = run_dir / f"results_{variant}_seed{seed}.json"
            if results_file.exists():
                with open(results_file, 'r') as f:
                    data = json.load(f)
                
                # Vérifier que les résultats test sont présents
                if "test" in data and "macro_auc" in data["test"]:
                    results[variant][seed] = data
    
    return dict(results)


def extract_metrics(results: Dict[str, Dict[int, Dict]]) -> Dict[str, Dict[str, np.ndarray]]:
    """
    Extrait les métriques pour analyse statistique.
    
    Returns:
        Dict[variant]["metric_name"] = array of values across seeds
    """
    metrics = defaultdict(lambda: defaultdict(list))
    
    for variant, seed_results in results.items():
        for seed, data in sorted(seed_results.items()):
            test = data.get("test", {})
            per_class = data.get("per_class", {})
            
            # Métriques globales
            metrics[variant]["macro_auc"].append(test.get("macro_auc", np.nan))
            metrics[variant]["macro_f1_optimal"].append(test.get("macro_f1_optimal", np.nan))
            metrics[variant]["macro_f1_fixed"].append(test.get("macro_f1_fixed", np.nan))
            metrics[variant]["auc_ecg_only"].append(test.get("auc_ecg_only", np.nan))
            metrics[variant]["auc_fused_only"].append(test.get("auc_fused_only", np.nan))
            metrics[variant]["delta_meta_auc"].append(test.get("delta_meta_auc", np.nan))
            metrics[variant]["w_fused"].append(test.get("w_fused", np.nan))
            
            # Métriques par classe
            for cls in DS5_LABELS:
                cls_data = per_class.get(cls, {})
                metrics[variant][f"auc_{cls}"].append(cls_data.get("auc", np.nan))
                metrics[variant][f"f1_{cls}"].append(cls_data.get("f1", np.nan))
    
    # Convertir en arrays numpy
    return {
        variant: {metric: np.array(values) for metric, values in metrics_dict.items()}
        for variant, metrics_dict in metrics.items()
    }


# ============================================================================
# STATISTIQUES
# ============================================================================

def bootstrap_ci(
    data: np.ndarray,
    rng: np.random.Generator,
    n_bootstrap: int = N_BOOTSTRAP,
    confidence: float = CONFIDENCE_LEVEL,
) -> Tuple[float, float]:
    """Calcule l'intervalle de confiance par bootstrap."""
    if len(data) < 2 or np.all(np.isnan(data)):
        return (np.nan, np.nan)
    
    data = data[~np.isnan(data)]
    if len(data) < 2:
        return (np.nan, np.nan)
    
    bootstrap_means = np.array([
        np.mean(rng.choice(data, size=len(data), replace=True))
        for _ in range(n_bootstrap)
    ])
    
    alpha = 1 - confidence
    ci_low = np.percentile(bootstrap_means, 100 * alpha / 2)
    ci_high = np.percentile(bootstrap_means, 100 * (1 - alpha / 2))
    
    return (ci_low, ci_high)


def wilcoxon_test(data1: np.ndarray, data2: np.ndarray) -> Tuple[float, float]:
    """
    Test de Wilcoxon signed-rank pour données appariées.
    
    Returns:
        (statistic, p_value)
    """
    # Filtrer les NaN (doivent être appariés)
    mask = ~(np.isnan(data1) | np.isnan(data2))
    d1, d2 = data1[mask], data2[mask]
    
    if len(d1) < 5:
        warnings.warn("Moins de 5 paires valides pour Wilcoxon")
        return (np.nan, np.nan)
    
    try:
        stat, pval = stats.wilcoxon(d1, d2, alternative='two-sided')
        return (stat, pval)
    except:
        return (np.nan, np.nan)


def compute_statistics(
    metrics: Dict[str, Dict[str, np.ndarray]],
    n_bootstrap: int = N_BOOTSTRAP,
    confidence: float = CONFIDENCE_LEVEL,
    bootstrap_seed: int = 2026,
) -> Dict[str, Any]:
    """
    Calcule toutes les statistiques pour chaque variante et métrique.
    """
    statistics = {}
    rng = np.random.default_rng(bootstrap_seed)
    
    for variant in VARIANTS:
        if variant not in metrics:
            continue
            
        statistics[variant] = {}
        
        for metric_name, values in metrics[variant].items():
            valid = values[~np.isnan(values)]
            
            if len(valid) == 0:
                statistics[variant][metric_name] = {
                    "n": 0,
                    "mean": np.nan,
                    "std": np.nan,
                    "ci_low": np.nan,
                    "ci_high": np.nan,
                    "min": np.nan,
                    "max": np.nan
                }
            else:
                ci_low, ci_high = bootstrap_ci(
                    valid,
                    rng=rng,
                    n_bootstrap=n_bootstrap,
                    confidence=confidence,
                )
                statistics[variant][metric_name] = {
                    "n": len(valid),
                    "mean": np.mean(valid),
                    "std": np.std(valid, ddof=1) if len(valid) > 1 else 0,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "min": np.min(valid),
                    "max": np.max(valid),
                    "values": valid.tolist()
                }
    
    return statistics


def compute_pairwise_tests(metrics: Dict[str, Dict[str, np.ndarray]]) -> Dict[str, Dict]:
    """
    Effectue les tests de Wilcoxon entre paires de variantes.
    """
    tests = {}
    pairs = [
        ("none", "demo"),
        ("none", "demo+anthro"),
        ("demo", "demo+anthro")
    ]
    
    key_metrics = ["macro_auc", "macro_f1_optimal"] + [f"auc_{c}" for c in DS5_LABELS] + [f"f1_{c}" for c in DS5_LABELS]
    
    for v1, v2 in pairs:
        if v1 not in metrics or v2 not in metrics:
            continue
            
        pair_key = f"{v1}_vs_{v2}"
        tests[pair_key] = {}
        
        for metric in key_metrics:
            if metric in metrics[v1] and metric in metrics[v2]:
                stat, pval = wilcoxon_test(metrics[v1][metric], metrics[v2][metric])
                
                # Différence moyenne
                d1, d2 = metrics[v1][metric], metrics[v2][metric]
                mask = ~(np.isnan(d1) | np.isnan(d2))
                diff = np.mean(d2[mask] - d1[mask]) if mask.any() else np.nan
                
                tests[pair_key][metric] = {
                    "statistic": stat,
                    "p_value": pval,
                    "significant_0.05": pval < 0.05 if not np.isnan(pval) else False,
                    "significant_0.01": pval < 0.01 if not np.isnan(pval) else False,
                    "mean_diff": diff
                }
    
    return tests


# ============================================================================
# GÉNÉRATION DE TABLEAUX
# ============================================================================

def format_value(mean: float, std: float, precision: int = 4) -> str:
    """Formate une valeur avec ± écart-type."""
    if np.isnan(mean):
        return "N/A"
    return f"{mean:.{precision}f} ± {std:.{precision}f}"


def format_with_significance(mean: float, std: float, pval: float, 
                             precision: int = 4, vs_baseline: bool = False) -> str:
    """Formate une valeur avec indicateur de significativité."""
    if np.isnan(mean):
        return "N/A"
    
    val = f"{mean:.{precision}f} ± {std:.{precision}f}"
    
    if vs_baseline and not np.isnan(pval):
        if pval < 0.01:
            val += "**"
        elif pval < 0.05:
            val += "*"
    
    return val


def generate_main_table_markdown(stats: Dict, tests: Dict) -> str:
    """Génère le Tableau 1 principal en Markdown."""
    
    lines = [
        "## Tableau 1. Performances sur le jeu de test (fold 10) - Validation multi-graines",
        "",
        "| Méthode | Macro AUC | Macro F1 | n |",
        "|---------|-----------|----------|---|"
    ]
    
    for variant in VARIANTS:
        if variant not in stats:
            continue
            
        label = VARIANT_LABELS[variant]
        auc = stats[variant].get("macro_auc", {})
        f1 = stats[variant].get("macro_f1_optimal", {})
        n = auc.get("n", 0)
        
        # Récupérer p-value vs baseline (none)
        if variant == "none":
            auc_str = format_value(auc.get("mean", np.nan), auc.get("std", np.nan))
            f1_str = format_value(f1.get("mean", np.nan), f1.get("std", np.nan))
        else:
            test_key = f"none_vs_{variant}"
            pval_auc = tests.get(test_key, {}).get("macro_auc", {}).get("p_value", np.nan)
            pval_f1 = tests.get(test_key, {}).get("macro_f1_optimal", {}).get("p_value", np.nan)
            
            auc_str = format_with_significance(
                auc.get("mean", np.nan), auc.get("std", np.nan), pval_auc, vs_baseline=True
            )
            f1_str = format_with_significance(
                f1.get("mean", np.nan), f1.get("std", np.nan), pval_f1, vs_baseline=True
            )
        
        lines.append(f"| {label} | {auc_str} | {f1_str} | {n} |")
    
    lines.extend([
        "",
        "*p < 0.05; **p < 0.01 (test de Wilcoxon signed-rank vs ECG seul)",
        ""
    ])
    
    return "\n".join(lines)


def generate_perclass_table_markdown(stats: Dict, tests: Dict) -> str:
    """Génère le tableau des performances par classe en Markdown."""
    
    lines = [
        "## Tableau 2. Performances par classe - Validation multi-graines",
        "",
        "### AUC par classe",
        "",
        "| Classe | ECG seul | ECG + demo | ECG + complet |",
        "|--------|----------|------------|---------------|"
    ]
    
    for cls in DS5_LABELS:
        row = [cls]
        for variant in VARIANTS:
            if variant not in stats:
                row.append("N/A")
                continue
            
            metric = f"auc_{cls}"
            data = stats[variant].get(metric, {})
            
            if variant == "none":
                val = format_value(data.get("mean", np.nan), data.get("std", np.nan))
            else:
                test_key = f"none_vs_{variant}"
                pval = tests.get(test_key, {}).get(metric, {}).get("p_value", np.nan)
                val = format_with_significance(
                    data.get("mean", np.nan), data.get("std", np.nan), pval, vs_baseline=True
                )
            row.append(val)
        
        lines.append("| " + " | ".join(row) + " |")
    
    lines.extend([
        "",
        "### F1 par classe",
        "",
        "| Classe | ECG seul | ECG + demo | ECG + complet |",
        "|--------|----------|------------|---------------|"
    ])
    
    for cls in DS5_LABELS:
        row = [cls]
        for variant in VARIANTS:
            if variant not in stats:
                row.append("N/A")
                continue
            
            metric = f"f1_{cls}"
            data = stats[variant].get(metric, {})
            
            if variant == "none":
                val = format_value(data.get("mean", np.nan), data.get("std", np.nan))
            else:
                test_key = f"none_vs_{variant}"
                pval = tests.get(test_key, {}).get(metric, {}).get("p_value", np.nan)
                val = format_with_significance(
                    data.get("mean", np.nan), data.get("std", np.nan), pval, vs_baseline=True
                )
            row.append(val)
        
        lines.append("| " + " | ".join(row) + " |")
    
    lines.extend([
        "",
        "*p < 0.05; **p < 0.01 (test de Wilcoxon signed-rank vs ECG seul)",
        ""
    ])
    
    return "\n".join(lines)


def generate_latex_table(stats: Dict, tests: Dict) -> str:
    """Génère le Tableau 1 en LaTeX pour l'article."""
    
    lines = [
        "\\begin{table}[htbp]",
        "\\centering",
        "\\caption{Performances sur le jeu de test (fold 10) avec validation multi-graines. "
        "Les résultats sont présentés sous forme moyenne $\\pm$ écart-type sur 10 graines aléatoires. "
        "$^*p < 0.05$; $^{**}p < 0.01$ (test de Wilcoxon signed-rank vs ECG seul).}",
        "\\label{tab:results_multiseed}",
        "\\begin{tabular}{lccc}",
        "\\toprule",
        "\\textbf{Méthode} & \\textbf{Macro AUC} & \\textbf{Macro F1} & \\textbf{n} \\\\",
        "\\midrule"
    ]
    
    for variant in VARIANTS:
        if variant not in stats:
            continue
            
        label = VARIANT_LABELS[variant]
        auc = stats[variant].get("macro_auc", {})
        f1 = stats[variant].get("macro_f1_optimal", {})
        n = auc.get("n", 0)
        
        mean_auc = auc.get("mean", np.nan)
        std_auc = auc.get("std", np.nan)
        mean_f1 = f1.get("mean", np.nan)
        std_f1 = f1.get("std", np.nan)
        
        # Significativité
        sig_auc, sig_f1 = "", ""
        if variant != "none":
            test_key = f"none_vs_{variant}"
            pval_auc = tests.get(test_key, {}).get("macro_auc", {}).get("p_value", np.nan)
            pval_f1 = tests.get(test_key, {}).get("macro_f1_optimal", {}).get("p_value", np.nan)
            
            if not np.isnan(pval_auc):
                if pval_auc < 0.01:
                    sig_auc = "$^{**}$"
                elif pval_auc < 0.05:
                    sig_auc = "$^{*}$"
            
            if not np.isnan(pval_f1):
                if pval_f1 < 0.01:
                    sig_f1 = "$^{**}$"
                elif pval_f1 < 0.05:
                    sig_f1 = "$^{*}$"
        
        auc_str = f"${mean_auc:.4f} \\pm {std_auc:.4f}${sig_auc}" if not np.isnan(mean_auc) else "N/A"
        f1_str = f"${mean_f1:.4f} \\pm {std_f1:.4f}${sig_f1}" if not np.isnan(mean_f1) else "N/A"
        
        lines.append(f"{label} & {auc_str} & {f1_str} & {n} \\\\")
    
    lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
        "\\end{table}"
    ])
    
    return "\n".join(lines)


def generate_gains_summary(stats: Dict, tests: Dict) -> str:
    """Génère un résumé des gains avec significativité."""
    
    lines = [
        "## Résumé des gains (ECG + complet vs ECG seul)",
        ""
    ]
    
    if "none" not in stats or "demo+anthro" not in stats:
        return "Données insuffisantes pour calculer les gains."
    
    metrics_to_compare = [
        ("macro_auc", "Macro AUC"),
        ("macro_f1_optimal", "Macro F1"),
    ] + [(f"f1_{c}", f"F1 {c}") for c in DS5_LABELS]
    
    lines.append("| Métrique | Baseline | Complet | Gain absolu | Gain relatif | p-value |")
    lines.append("|----------|----------|---------|-------------|--------------|---------|")
    
    test_key = "none_vs_demo+anthro"
    
    for metric_key, metric_label in metrics_to_compare:
        baseline = stats["none"].get(metric_key, {})
        complete = stats["demo+anthro"].get(metric_key, {})
        test_result = tests.get(test_key, {}).get(metric_key, {})
        
        mean_base = baseline.get("mean", np.nan)
        mean_comp = complete.get("mean", np.nan)
        
        if not np.isnan(mean_base) and not np.isnan(mean_comp):
            gain_abs = mean_comp - mean_base
            gain_rel = 100 * gain_abs / mean_base if mean_base != 0 else np.nan
            pval = test_result.get("p_value", np.nan)
            
            sig = ""
            if not np.isnan(pval):
                if pval < 0.01:
                    sig = "**"
                elif pval < 0.05:
                    sig = "*"
            
            pval_str = f"{pval:.4f}{sig}" if not np.isnan(pval) else "N/A"
            
            lines.append(
                f"| {metric_label} | {mean_base:.4f} | {mean_comp:.4f} | "
                f"{gain_abs:+.4f} | {gain_rel:+.2f}% | {pval_str} |"
            )
    
    lines.extend([
        "",
        "*p < 0.05; **p < 0.01",
        ""
    ])
    
    return "\n".join(lines)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Analyse statistique des résultats multi-graines EZNX_ATLAS_A'
    )
    parser.add_argument(
        '--runs_dir',
        type=str,
        required=True,
        help='Répertoire contenant les runs'
    )
    parser.add_argument(
        '--output_dir',
        type=str,
        default=None,
        help='Répertoire de sortie pour les rapports (défaut: runs_dir)'
    )
    parser.add_argument(
        '--n_bootstrap',
        type=int,
        default=N_BOOTSTRAP,
        help=f'Nombre d\'itérations bootstrap (défaut: {N_BOOTSTRAP})'
    )
    parser.add_argument(
        '--bootstrap_seed',
        type=int,
        default=2026,
        help='Graine aleatoire pour rendre le bootstrap deterministe'
    )
    
    args = parser.parse_args()
    
    runs_dir = Path(args.runs_dir)
    output_dir = Path(args.output_dir) if args.output_dir else runs_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("ANALYSE STATISTIQUE MULTI-GRAINES")
    print("=" * 80)
    print(f"Runs dir:    {runs_dir}")
    print(f"Output dir:  {output_dir}")
    print(f"Bootstrap:   {args.n_bootstrap} iterations")
    print(f"Seed:        {args.bootstrap_seed}")
    print("=" * 80)
    
    # 1. Charger les résultats
    print("\n[1/4] Chargement des résultats...")
    results = load_all_results(runs_dir)
    
    for variant in VARIANTS:
        n_seeds = len(results.get(variant, {}))
        seeds = sorted(results.get(variant, {}).keys())
        print(f"   {variant}: {n_seeds} seeds {seeds if n_seeds <= 10 else '...'}")
    
    if not results:
        print("\nERREUR: Aucun résultat trouvé!")
        return
    
    # 2. Extraire les métriques
    print("\n[2/4] Extraction des métriques...")
    metrics = extract_metrics(results)
    
    # 3. Calculer les statistiques
    print("\n[3/4] Calcul des statistiques...")
    stats = compute_statistics(
        metrics,
        n_bootstrap=args.n_bootstrap,
        confidence=CONFIDENCE_LEVEL,
        bootstrap_seed=args.bootstrap_seed,
    )
    tests = compute_pairwise_tests(metrics)
    
    # Afficher résumé
    print("\n" + "-" * 80)
    print("RÉSUMÉ STATISTIQUE")
    print("-" * 80)
    
    for variant in VARIANTS:
        if variant not in stats:
            continue
        print(f"\n{VARIANT_LABELS[variant]}:")
        auc = stats[variant].get("macro_auc", {})
        f1 = stats[variant].get("macro_f1_optimal", {})
        print(f"   Macro AUC: {auc.get('mean', np.nan):.4f} ± {auc.get('std', np.nan):.4f} "
              f"[{auc.get('ci_low', np.nan):.4f}, {auc.get('ci_high', np.nan):.4f}] (n={auc.get('n', 0)})")
        print(f"   Macro F1:  {f1.get('mean', np.nan):.4f} ± {f1.get('std', np.nan):.4f} "
              f"[{f1.get('ci_low', np.nan):.4f}, {f1.get('ci_high', np.nan):.4f}]")
    
    # Tests de significativité
    print("\n" + "-" * 80)
    print("TESTS DE SIGNIFICATIVITÉ (Wilcoxon signed-rank)")
    print("-" * 80)
    
    for pair_key, pair_tests in tests.items():
        v1, v2 = pair_key.replace("_vs_", " vs ").split(" vs ")
        print(f"\n{VARIANT_LABELS.get(v1, v1)} vs {VARIANT_LABELS.get(v2, v2)}:")
        
        for metric in ["macro_auc", "macro_f1_optimal"]:
            if metric in pair_tests:
                t = pair_tests[metric]
                sig = "**" if t.get("significant_0.01") else ("*" if t.get("significant_0.05") else "")
                print(f"   {metric}: p = {t.get('p_value', np.nan):.4f}{sig} "
                      f"(diff = {t.get('mean_diff', np.nan):+.4f})")
    
    # 4. Générer les rapports
    print("\n[4/4] Génération des rapports...")
    
    # Markdown
    md_content = [
        "# Analyse Statistique Multi-Graines - EZNX_ATLAS_A",
        "",
        f"*Généré le {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        generate_main_table_markdown(stats, tests),
        generate_perclass_table_markdown(stats, tests),
        generate_gains_summary(stats, tests)
    ]
    
    md_path = output_dir / "statistical_analysis_report.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(md_content))
    print(f"   Rapport Markdown: {md_path}")
    
    # LaTeX
    latex_content = generate_latex_table(stats, tests)
    latex_path = output_dir / "table_results_latex.tex"
    with open(latex_path, 'w', encoding='utf-8') as f:
        f.write(latex_content)
    print(f"   Table LaTeX: {latex_path}")
    
    # JSON complet
    full_report = {
        "statistics": stats,
        "pairwise_tests": tests,
        "config": {
            "n_bootstrap": args.n_bootstrap,
            "bootstrap_seed": args.bootstrap_seed,
            "confidence_level": CONFIDENCE_LEVEL
        }
    }
    
    # Convertir les valeurs numpy pour JSON
    
    # def convert_numpy(obj):
        # if isinstance(obj, np.ndarray):
            # return obj.tolist()
        # if isinstance(obj, (np.floating, np.integer)):
            # return float(obj) if isinstance(obj, np.floating) else int(obj)
        # if isinstance(obj, dict):
            # return {k: convert_numpy(v) for k, v in obj.items()}
        # if isinstance(obj, list):
            # return [convert_numpy(i) for i in obj]
        # return obj
        
    def convert_numpy(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
    if isinstance(obj, (np.bool_,)):   # Keep NumPy booleans JSON-serializable.
        return bool(obj)
        if isinstance(obj, dict):
            return {k: convert_numpy(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert_numpy(i) for i in obj]
        return obj
    
    json_path = output_dir / "statistical_analysis_full.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(convert_numpy(full_report), f, indent=2, ensure_ascii=False)
    print(f"   Rapport JSON complet: {json_path}")
    
    print("\n" + "=" * 80)
    print("[OK] Analyse terminee.")
    print("=" * 80)
    
    # Afficher le tableau principal formaté
    print("\n" + generate_main_table_markdown(stats, tests))


if __name__ == "__main__":
    main()

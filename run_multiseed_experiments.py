# ============================================================================
# run_multiseed_experiments.py - Orchestrateur d'expériences multi-graines
# ============================================================================
# Lance automatiquement les 3 variantes × 10 seeds = 30 entraînements
# Gère les erreurs et permet de reprendre les expériences interrompues
# ============================================================================

import subprocess
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Tuple
import time


# ============================================================================
# CONFIGURATION
# ============================================================================

# Seeds pour validation statistique (10 seeds recommandées)
DEFAULT_SEEDS = [2024, 2025, 2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]

# Variantes d'ablation
VARIANTS = ["none", "demo", "demo+anthro"]

# Script d'entraînement
PROJECT_ROOT = Path(__file__).resolve().parent
TRAINING_SCRIPT = PROJECT_ROOT / "atlas_a_v5_multiseed.py"


def check_completed(runs_dir: Path, variant: str, seed: int) -> bool:
    """Vérifie si un run est déjà complété (fichier JSON existe et contient des résultats test)."""
    results_file = runs_dir / f"ATLAS_A_v5_{variant}_seed{seed}" / f"results_{variant}_seed{seed}.json"
    
    if not results_file.exists():
        return False
    
    try:
        with open(results_file, 'r') as f:
            data = json.load(f)
        # Vérifie que les résultats test sont présents
        return "test" in data and "macro_auc" in data.get("test", {})
    except:
        return False


def run_experiment(
    variant: str, 
    seed: int, 
    data_root: str,
    index_path: str,
    runs_dir: str,
    dry_run: bool = False
) -> Tuple[bool, str]:
    """Lance un entraînement unique et retourne (succès, message)."""
    
    cmd = [
        sys.executable,
        str(TRAINING_SCRIPT),
        "--variant", variant,
        "--seed", str(seed),
        "--data_root", data_root,
        "--index_path", index_path,
        "--runs_dir", runs_dir
    ]
    
    if dry_run:
        print(f"   [DRY-RUN] {' '.join(cmd)}")
        return True, "Dry run - not executed"
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600 * 4  # 4 heures max par run
        )
        
        if result.returncode == 0:
            return True, "Success"
        else:
            return False, f"Exit code {result.returncode}: {result.stderr[-500:]}"
            
    except subprocess.TimeoutExpired:
        return False, "Timeout (>4h)"
    except Exception as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(
        description='Orchestrateur d\'expériences multi-graines EZNX_ATLAS_A',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  # Lancer toutes les expériences (30 runs)
  python run_multiseed_experiments.py --data_root /path/to/ptb-xl --runs_dir ./runs
  
  # Lancer seulement une variante
  python run_multiseed_experiments.py --variants demo+anthro --data_root /path/to/ptb-xl
  
        """
    )
    
    # Arguments obligatoires
    parser.add_argument(
        '--data_root',
        type=str,
        required=True,
        help='Chemin vers le répertoire PTB-XL'
    )
    
    # Arguments optionnels
    parser.add_argument(
        '--index_path',
        type=str,
        default=str(PROJECT_ROOT / 'data' / 'index_complete.parquet'),
        help='Chemin vers le fichier index parquet (defaut: <repo>/data/index_complete.parquet)'
    )
    parser.add_argument(
        '--runs_dir',
        type=str,
        default=str(PROJECT_ROOT / 'runs'),
        help='Repertoire de sortie pour les runs (defaut: <repo>/runs)'
    )
    parser.add_argument(
        '--seeds',
        type=int,
        nargs='+',
        default=DEFAULT_SEEDS,
        help=f'Liste des seeds à utiliser (défaut: {DEFAULT_SEEDS})'
    )
    parser.add_argument(
        '--variants',
        type=str,
        nargs='+',
        choices=VARIANTS,
        default=VARIANTS,
        help=f'Variantes à entraîner (défaut: {VARIANTS})'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Ne relance pas les runs déjà complétés'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Affiche les commandes sans les exécuter'
    )
    parser.add_argument(
        '--sequential',
        action='store_true',
        help='Option conservee pour compatibilite; l execution actuelle est sequentielle.'
    )
    
    args = parser.parse_args()
    
    runs_dir = Path(args.runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    
    # Liste des expériences à lancer
    experiments = []
    for variant in args.variants:
        for seed in args.seeds:
            experiments.append((variant, seed))
    
    total = len(experiments)
    
    print("=" * 80)
    print("ORCHESTRATEUR D'EXPÉRIENCES MULTI-GRAINES")
    print("=" * 80)
    print(f"Data root:   {args.data_root}")
    print(f"Index:       {args.index_path}")
    print(f"Output:      {runs_dir}")
    print(f"Variantes:   {args.variants}")
    print(f"Seeds:       {args.seeds}")
    print(f"Total runs:  {total}")
    print(f"Mode:        {'DRY-RUN' if args.dry_run else 'EXECUTION'}")
    print(f"Resume:      {args.resume}")
    print("=" * 80)
    
    # Filtrer les expériences déjà complétées si --resume
    if args.resume:
        pending = []
        for variant, seed in experiments:
            if not check_completed(runs_dir, variant, seed):
                pending.append((variant, seed))
            else:
                print(f"   [SKIP] {variant} seed={seed} (déjà complété)")
        experiments = pending
        print(f"\nExpériences restantes: {len(experiments)}/{total}")
    
    if not experiments:
        print("\n[OK] Toutes les experiences sont deja completees.")
        return
    
    # Log des expériences
    log_file = runs_dir / f"experiment_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    # Exécution
    print("\n" + "-" * 80)
    print("LANCEMENT DES EXPÉRIENCES")
    print("-" * 80)
    
    results_summary = []
    start_time = time.time()
    
    for i, (variant, seed) in enumerate(experiments, 1):
        exp_start = time.time()
        print(f"\n[{i}/{len(experiments)}] Variante: {variant}, Seed: {seed}")
        print("-" * 40)
        
        success, message = run_experiment(
            variant=variant,
            seed=seed,
            data_root=args.data_root,
            index_path=args.index_path,
            runs_dir=str(runs_dir),
            dry_run=args.dry_run
        )
        
        exp_duration = time.time() - exp_start
        status = "[OK]" if success else "[FAIL]"
        
        result = {
            "variant": variant,
            "seed": seed,
            "success": success,
            "message": message,
            "duration_seconds": exp_duration
        }
        results_summary.append(result)
        
        print(f"   {status} {message} ({exp_duration/60:.1f} min)")
        
        # Log en temps réel
        with open(log_file, 'a') as f:
            f.write(f"{datetime.now().isoformat()} | {variant} | seed={seed} | {status} | {message} | {exp_duration:.0f}s\n")
    
    # Résumé final
    total_time = time.time() - start_time
    successes = sum(1 for r in results_summary if r["success"])
    failures = len(results_summary) - successes
    
    print("\n" + "=" * 80)
    print("RÉSUMÉ FINAL")
    print("=" * 80)
    print(f"Total exécutées: {len(results_summary)}")
    print(f"Réussites:       {successes}")
    print(f"Échecs:          {failures}")
    print(f"Temps total:     {total_time/3600:.1f} heures")
    print(f"Log:             {log_file}")
    
    if failures > 0:
        print("\nExpériences échouées:")
        for r in results_summary:
            if not r["success"]:
                print(f"   - {r['variant']} seed={r['seed']}: {r['message']}")
    
    # Sauvegarder le résumé JSON
    summary_file = runs_dir / f"experiment_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_file, 'w') as f:
        json.dump({
            "config": {
                "data_root": args.data_root,
                "index_path": args.index_path,
                "runs_dir": str(runs_dir),
                "seeds": args.seeds,
                "variants": args.variants
            },
            "results": results_summary,
            "summary": {
                "total": len(results_summary),
                "successes": successes,
                "failures": failures,
                "total_time_hours": total_time / 3600
            }
        }, f, indent=2)
    
    print(f"\nRésumé sauvegardé: {summary_file}")
    print("=" * 80)
    
    if failures > 0:
        print("\n[WARN] Certaines experiences ont echoue. Utilisez --resume pour les relancer.")
        sys.exit(1)
    else:
        print("\n[OK] Toutes les experiences sont terminees avec succes.")
        print("  Lancez maintenant: python analyze_multiseed_results.py --runs_dir", runs_dir)


if __name__ == "__main__":
    main()

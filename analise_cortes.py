# -*- coding: utf-8 -*-
"""Linha de comando: python analise_cortes.py --pasta DADOS  (gera Base_Cortes.xlsx na pasta)."""
import argparse
import os

from cortes import Analise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pasta", required=True, help="pasta com os arquivos Atividades-*, o cadastro e (opcional) o catálogo")
    p.add_argument("--hoje", help="data usada na régua (AAAA-MM-DD); padrão: hoje")
    args = p.parse_args()
    analise = Analise(args.pasta, progresso=lambda pct, texto: print(f"{pct:3d}% {texto}"))
    dados = analise.executar(args.hoje)
    for k, v in dados["info"].items():
        print(f"- {k}: {v}")
    destino = os.path.join(args.pasta, "Base_Cortes.xlsx")
    with open(destino, "wb") as f:
        f.write(analise.excel())
    print(f"Planilha gravada em {destino}")


if __name__ == "__main__":
    main()

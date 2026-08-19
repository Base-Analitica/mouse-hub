import sys
from pathlib import Path

# O projeto não tem pyproject instalado na máquina do usuário em
# runtime; os testes importam o core diretamente do repositório.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

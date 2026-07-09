# Garante que os módulos do projeto são importáveis nos testes
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

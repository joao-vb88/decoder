import os

# --- Mapa QWERTY com coordenadas (permite diagonais) ---
KEYS = {
    'q':(0,0),'w':(0,1),'e':(0,2),'r':(0,3),'t':(0,4),
    'y':(0,5),'u':(0,6),'i':(0,7),'o':(0,8),'p':(0,9),
    'a':(1,0.5),'s':(1,1.5),'d':(1,2.5),'f':(1,3.5),
    'g':(1,4.5),'h':(1,5.5),'j':(1,6.5),'k':(1,7.5),'l':(1,8.5),
    'z':(2,1),'x':(2,2),'c':(2,3),'v':(2,4),
    'b':(2,5),'n':(2,6),'m':(2,7),
}

VIZ = {}
for k1,(r1,c1) in KEYS.items():
    nb = []
    for k2,(r2,c2) in KEYS.items():
        if k1 == k2:
            continue
        d = ((r1-r2)**2 + (c1-c2)**2) ** 0.5
        if d <= 1.6:
            nb.append(k2)
    VIZ[k1] = nb


# --- Trie ---
class TrieNode:
    __slots__ = ('children','word')
    def __init__(self):
        self.children = {}
        self.word = None


class Decoder:
    def __init__(self, words, freq=None):
        self.freq = freq or {}
        self.root = TrieNode()
        for w in words:
            w = w.strip().lower()
            if not w:
                continue
            node = self.root
            for ch in w:
                node = node.children.setdefault(ch, TrieNode())
            node.word = w

    def cands(self, ch):
        return VIZ.get(ch, [ch])

    def decode_token(self, token, limit=None):
        token = token.lower()
        results = []

        def dfs(i, node, path):
            if i == len(token):
                if node.word is not None:
                    results.append(''.join(path))
                return
            for c in self.cands(token[i]):
                child = node.children.get(c)
                if child is not None:
                    path.append(c)
                    dfs(i+1, child, path)
                    path.pop()

        dfs(0, self.root, [])

        # Ordena por frequência (maior primeiro); sem freq vai pro fim
        results.sort(key=lambda w: self.freq.get(w, 0), reverse=True)

        if limit is not None:
            results = results[:limit]
        return results

    def decode(self, phrase, limit=None):
        return [self.decode_token(tok, limit) for tok in phrase.split()]


# --- Carregadores ---
def carregar_dic(caminho="br-sem-acentos.txt"):
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            return [l.strip().lower() for l in f if l.strip()]
    print("[aviso] br-sem-acentos.txt não encontrado — usando lista pequena.")
    return ["meu","nome","arvore","muda","tiro","nicho","casa","bola"]


def carregar_freq(caminho="frequencia.txt"):
    freq = {}
    if not os.path.exists(caminho):
        print("[aviso] frequencia.txt não encontrado — sem ranking.")
        return freq
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            partes = linha.split()
            if len(partes) < 2:
                continue
            palavra, cnt = partes[0].lower(), partes[1]
            try:
                freq[palavra] = int(cnt)
            except ValueError:
                continue
    return freq


# --- Main ---
if __name__ == "__main__":
    LIMITE = None       # None = sem limite; ou ex.: 10

    palavras = carregar_dic()
    freq = carregar_freq()
    print(f"[dic]  {len(palavras)} palavras")
    print(f"[freq] {len(freq)} palavras com frequência")

    dec = Decoder(palavras, freq=freq)
    print("Digite uma frase (ou 'sair'):")

    while True:
        frase = input("> ").strip()
        if frase.lower() in ("sair", "exit"):
            break
        if not frase:
            continue

        tokens = frase.split()
        listas = dec.decode(frase, limit=LIMITE)
        for tok, matches in zip(tokens, listas):
            if not matches:
                print(f"  {tok}: (nenhuma)")
            else:
                top = matches[:10]
                extra = "" if len(matches) <= 10 else f"  (+{len(matches)-10})"
                print(f"  {tok}: {len(matches)} → {', '.join(top)}{extra}")
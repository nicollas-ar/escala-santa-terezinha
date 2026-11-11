document.addEventListener("DOMContentLoaded", () => {
  const botao = document.getElementById("menu-botao");
  const navegacao = document.getElementById("navegacao");
  botao?.addEventListener("click", () => {
    const aberto = navegacao.classList.toggle("aberto");
    botao.setAttribute("aria-expanded", String(aberto));
    botao.textContent = aberto ? "✕" : "☰";
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && navegacao?.classList.contains("aberto")) {
      navegacao.classList.remove("aberto");
      botao?.setAttribute("aria-expanded", "false");
      if (botao) botao.textContent = "☰";
      botao?.focus();
    }
  });
  navegacao?.querySelectorAll("a").forEach(a => a.addEventListener("click", () => {
    navegacao.classList.remove("aberto");
    botao?.setAttribute("aria-expanded", "false");
    if (botao) botao.textContent = "☰";
  }));
  const listaFuncoes = document.getElementById("lista-funcoes");
  const adicionarFuncao = document.getElementById("adicionar-funcao");
  const quantidade = document.querySelector('input[name="quantidade"]');
  const contadorFuncoes = document.getElementById("contador-funcoes");
  function atualizarFuncoes() {
    if (!listaFuncoes) return;
    const n = listaFuncoes.querySelectorAll(".linha-funcao").length;
    const alvo = Number(quantidade?.value || 0);
    if (contadorFuncoes) contadorFuncoes.textContent = n + " de " + alvo + " funções adicionadas";
    if (adicionarFuncao) adicionarFuncao.disabled = n >= 30 || (alvo > 0 && n >= alvo);
  }
  function criarFuncao(valor = "") {
    if (!listaFuncoes || listaFuncoes.children.length >= 30) return;
    const linha = document.createElement("div");
    linha.className = "linha-funcao";
    linha.style.cssText = "display:flex;gap:8px;align-items:center";
    const input = document.createElement("input");
    input.type = "text";
    input.name = "funcoes";
    input.maxLength = 45;
    input.required = true;
    input.placeholder = "Ex.: Missal";
    input.setAttribute("aria-label", "Nome da função");
    input.value = valor;
    const remover = document.createElement("button");
    remover.type = "button";
    remover.className = "btn btn-perigo btn-pequeno remover-funcao";
    remover.textContent = "Remover";
    linha.append(input, remover);
    listaFuncoes.append(linha);
    atualizarFuncoes();
    return input;
  }
  adicionarFuncao?.addEventListener("click", () => criarFuncao()?.focus());
  listaFuncoes?.addEventListener("click", e => {
    if (e.target.closest(".remover-funcao")) {
      e.target.closest(".linha-funcao").remove();
      atualizarFuncoes();
    }
  });
  quantidade?.addEventListener("input", atualizarFuncoes);
  if (listaFuncoes && !listaFuncoes.children.length) {
    criarFuncao("Missal");
  }
  atualizarFuncoes();
  document.querySelectorAll("[data-selecionar]").forEach(botao => {
    botao.addEventListener("click", () => {
      const selecionar = botao.dataset.selecionar === "todos";
      document.querySelectorAll('input[name="disponiveis"]').forEach(input => {
        input.checked = selecionar;
      });
    });
  });
  document.querySelectorAll("[data-cartao-escala]").forEach(botao => {
    botao.addEventListener("click", async () => {
      const status = botao.parentElement.querySelector(".status-compartilhar");
      if (status) status.textContent = "";
      try {
        const m = JSON.parse(botao.dataset.cartaoEscala);
        const arquivo = await desenharEscala(m);
        const dados = {files: [arquivo]};
        if (navigator.share && navigator.canShare?.(dados)) {
          try {
            await navigator.share(dados);
            return;
          } catch (erro) {
            if (erro.name === "AbortError") return;
          }
        }
        const url = URL.createObjectURL(arquivo);
        const a = document.createElement("a");
        a.href = url;
        a.download = arquivo.name;
        document.body.append(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 10000);
        if (status) status.textContent = "Imagem salva. Compartilhe pelo WhatsApp.";
      } catch (erro) {
        if (status) status.textContent = "Não foi possível gerar a imagem.";
      }
    });
  });
});
function linhasDeTexto(ctx, valor, largura) {
  const linhas = [];
  for (const p of String(valor).split("\n")) {
    let atual = "";
    for (const palavra of p.split(/\s+/)) {
      const teste = atual ? atual + " " + palavra : palavra;
      if (atual && ctx.measureText(teste).width > largura) {
        linhas.push(atual);
        atual = palavra;
      } else {
        atual = teste;
      }
    }
    linhas.push(atual);
  }
  return linhas;
}
async function desenharEscala(m) {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  const W = 900, margem = 60, largura = W - margem * 2;
  const blocos = [];
  let y = 60;
  function escrever(texto, fonte, cor, entrelinha, fundo) {
    ctx.font = fonte;
    const linhas = linhasDeTexto(ctx, texto, largura - (fundo ? 24 : 0));
    const topo = y;
    y += linhas.length * entrelinha + (fundo ? 16 : 8);
    blocos.push(() => {
      if (fundo) {
        ctx.fillStyle = "#f1f3f7";
        ctx.fillRect(margem - 12, topo - 8, largura + 24, linhas.length * entrelinha + 23);
      }
      ctx.fillStyle = cor;
      ctx.font = fonte;
      linhas.forEach((l, i) => ctx.fillText(l, margem + (fundo ? 12 : 0), topo + i * entrelinha));
    });
  }
  escrever("PARÓQUIA SANTA TEREZINHA DO MENINO JESUS", "bold 27px Arial", "#fff", 38);
  escrever("Escala de servidores", "bold 52px Georgia", "#fff", 68);
  escrever(m.nome, "bold 33px Arial", "#fff", 46);
  escrever(m.quando, "25px Arial", "#fff", 37);
  const divisor = y + 16;
  y = divisor + 44;
  m.equipe.forEach(([nome, funcao], i) => {
    escrever(String(i + 1).padStart(2, "0") + "   " + nome, "bold 31px Arial", "#162b4f", 42, true);
    escrever("        " + funcao, "25px Arial", "#54657a", 38);
    y += 10;
  });
  if (m.recado) {
    y += 12;
    escrever("ORIENTAÇÕES", "bold 23px Arial", "#8f5064", 35);
    escrever(m.recado, "25px Arial", "#283950", 37);
  }
  const H = Math.min(4096, y + 60);
  canvas.width = W; canvas.height = H;
  ctx.textBaseline = "top";
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = "#162b4f"; ctx.fillRect(0, 0, W, divisor);
  ctx.fillStyle = "#8f5064"; ctx.fillRect(0, divisor, W, 7);
  blocos.forEach(fn => fn());
  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => blob
      ? resolve(new File([blob], "escala-" + m.data + ".png", {type: "image/png"}))
      : reject(new Error("Não foi possível criar o cartão")), "image/png");
  });
}
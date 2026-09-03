// delete-blocks-from-date.js
const SENDGRID_API_KEY = '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';

const START_DATE = new Date('2026-06-01T03:00:00Z'); // 29/05 00:00 BRT
const END_DATE   = new Date('2026-06-02T03:00:00Z'); // 29/05 23:59 BRT

const START_UNIX = Math.floor(START_DATE.getTime() / 1000);
const END_UNIX   = Math.floor(END_DATE.getTime() / 1000);

const headers = {
  'Authorization': `Bearer ${SENDGRID_API_KEY}`,
  'Content-Type': 'application/json'
};

async function fetchBlocks(offset = 0) {
  const url = new URL('https://api.sendgrid.com/v3/suppression/blocks');
  url.searchParams.set('start_time', START_UNIX);
  url.searchParams.set('end_time', END_UNIX);
  url.searchParams.set('limit', 500);
  url.searchParams.set('offset', offset);

  const res = await fetch(url.toString(), { headers });
  if (!res.ok) throw new Error(`Erro ao buscar blocks: ${res.status} ${await res.text()}`);
  return res.json();
}

async function contarBlocks() {
  let total = 0;
  let offset = 0;
  let pagina = 0;
  let ultimoPrimeiroEmail = null;

  while (true) {
    const blocks = await fetchBlocks(offset);
    pagina++;
    console.log(`  página ${pagina}: ${blocks.length} registros (offset ${offset}, total parcial ${total + blocks.length})`);

    if (!blocks.length) break;

    // segurança: se a API ignorar offset e devolver sempre a mesma página, encerra para não loopar para sempre
    if (blocks[0].email === ultimoPrimeiroEmail) {
      console.log(`  (offset não avança — a API repetiu a mesma página; encerrando contagem)`);
      break;
    }
    ultimoPrimeiroEmail = blocks[0].email;

    total += blocks.length;
    offset += blocks.length;

    if (blocks.length < 500) break;
  }

  return total;
}

async function deleteBlocks(emails) {
  const res = await fetch('https://api.sendgrid.com/v3/suppression/blocks', {
    method: 'DELETE',
    headers,
    body: JSON.stringify({ emails })
  });
  if (!res.ok) throw new Error(`Erro ao deletar: ${res.status} ${await res.text()}`);
}

async function main() {
  console.log(`Contando blocks do período...`);
  const totalInicial = await contarBlocks();
  console.log(`Total encontrado: ${totalInicial} blocks\n`);

  if (!totalInicial) {
    console.log(`Nada para deletar.`);
    return;
  }

  let totalDeletados = 0;

  while (true) {
    let blocks;
    try {
      blocks = await fetchBlocks();
    } catch (err) {
      console.log(`Erro ao buscar blocks (${err.message}), tentando novamente em 5s...`);
      await new Promise(r => setTimeout(r, 5000));
      continue;
    }

    if (!blocks.length) break;

    const emails = blocks.map(b => b.email);
    console.log(`${emails.length} blocks encontrados, deletando... (faltam ~${totalInicial - totalDeletados})`);

    try {
      await deleteBlocks(emails);
    } catch (err) {
      console.log(`Erro ao deletar (${err.message}), tentando novamente em 5s...`);
      await new Promise(r => setTimeout(r, 5000));
      continue;
    }

    totalDeletados += emails.length;
    console.log(`✓ ${totalDeletados} deletados no total`);

    await new Promise(r => setTimeout(r, 1000));
  }

  console.log(`\n✅ Concluído! Total deletado: ${totalDeletados} blocks (estimativa inicial: ${totalInicial})`);
}

main().catch(console.error);
// Dependency-free static server for the exported site (apps/web/out), used by the browser tests.
import { createServer } from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import { extname, join, normalize, resolve } from 'node:path'

const root = resolve(process.argv[2] || 'out')
const port = Number(process.argv[3] || 4310)
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.json': 'application/json', '.txt': 'text/plain' }

createServer(async (req, res) => {
  const path = decodeURIComponent(new URL(req.url, 'http://x').pathname)
  let file = normalize(join(root, path))
  if (!file.startsWith(root)) { res.writeHead(403).end(); return }
  for (const candidate of [file, `${file}.html`, join(file, 'index.html')]) {
    if (await stat(candidate).then(info => info.isFile(), () => false)) { file = candidate; break }
  }
  try {
    const body = await readFile(file)
    res.writeHead(200, { 'Content-Type': types[extname(file)] || 'application/octet-stream' }).end(body)
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/html' }).end(await readFile(join(root, '404.html')).catch(() => 'Not found'))
  }
}).listen(port, () => console.log(`serving ${root} on ${port}`))

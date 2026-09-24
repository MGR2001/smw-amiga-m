-- oambot.lua - graba, por frame, lo que D8 necesita para estudiar los objetos
-- (AGENTS.md §9) mientras una persona juega en SuperMarioWorldSNESRecomp.
-- Lo carga y lo vacia tools/oamrec.py por el puerto Lua TCP.
--
-- Limites del protocolo (medidos): cada valor devuelto se corta a 1024
-- caracteres y una respuesta lleva como maximo 16 valores. Por eso los
-- registros son compactos y BOT_drain los entrega en trozos de <= 1000.
--
-- Registro por frame, campos separados por espacio:
--   frame_emu modo translevel camL1x camL1y camL2x camL2y mariox marioy powerup
--   oam   = entradas visibles (y != $F0): x y tile attr hi   (5 bytes hex c/u)
--   slots = ranuras activas: n estado numero xlo xhi ylo yhi (7 bytes hex c/u)
--   dp    = WRAM $0000-$00FF (joypad $15-$18, velocidades $7B/$7D, posicion
--           $94/$96, en el aire $72, direccion $76...)
--   w13   = WRAM $13C0-$14FF (subpixeles $13DA/$13DC, pose $13E0...)
--   dp y w13 son el oraculo de la fisica de Mario (etapa 8).
-- Con REC_ALL = true graba en cualquier modo (para probar en el titulo).
local r, r16 = mainmemory.read_u8, mainmemory.read_u16_le

local function hex(addr, len)
    local t = mainmemory.readbyterange(addr, len)
    local base = t[0] ~= nil and 0 or 1
    local s = {}
    for i = 0, len - 1 do s[#s + 1] = string.format("%02x", t[base + i]) end
    return table.concat(s)
end
event.unregisterbyname("oambot.in")
event.unregisterbyname("oambot.rec")
if REC_ALL == nil then REC_ALL = false end

BOT = {buf = {}, head = 1, frames = 0, lvframes = 0, done = false}

event.onframeend(function()
    if BOT.done then return end
    local mode = r(0x100)
    if mode ~= 0x14 and not REC_ALL then
        -- termina al salir de un nivel largo (no del mensaje de la intro)
        if BOT.lvframes > 600 and BOT.lastlevel ~= 0 then BOT.done = true end
        BOT.lvframes = 0
        return
    end
    BOT.frames = BOT.frames + 1
    BOT.lvframes = BOT.lvframes + 1
    BOT.lastlevel = r(0x13bf)
    local oam = mainmemory.readbyterange(0x200, 512)
    local hi = mainmemory.readbyterange(0x420, 128)
    local base = oam[0] ~= nil and 0 or 1
    local o = {}
    for i = 0, 127 do
        local y = oam[base + 4 * i + 1]
        if y ~= 0xf0 then
            o[#o + 1] = string.format("%02x%02x%02x%02x%02x", oam[base + 4 * i],
                y, oam[base + 4 * i + 2], oam[base + 4 * i + 3], hi[base + i])
        end
    end
    local s = {}
    for k = 0, 11 do
        local st = r(0x14c8 + k)
        if st ~= 0 then
            s[#s + 1] = string.format("%02x%02x%02x%02x%02x%02x%02x", k, st,
                r(0x9e + k), r(0xe4 + k), r(0x14e0 + k), r(0xd8 + k), r(0x14d4 + k))
        end
    end
    BOT.buf[#BOT.buf + 1] = table.concat({
        string.format("%d %02x %02x %04x %04x %04x %04x %04x %04x %02x",
            emu.framecount(), mode, r(0x13bf), r16(0x1462), r16(0x1464),
            r16(0x1466), r16(0x1468), r16(0x94), r16(0x96), r(0x19)),
        table.concat(o), table.concat(s), hex(0x0000, 256), hex(0x13c0, 320)}, " ") .. "\n"
end, "oambot.rec")

-- Hasta 16 trozos de <= 1000 caracteres con registros enteros.
function BOT_drain()
    local parts, cur, total = {}, {}, 0
    while BOT.head <= #BOT.buf do
        local rec = BOT.buf[BOT.head]
        if total + #rec > 15000 then break end
        total = total + #rec
        cur[#cur + 1] = rec
        BOT.buf[BOT.head] = false
        BOT.head = BOT.head + 1
    end
    local text = table.concat(cur)
    for i = 1, #text, 1000 do parts[#parts + 1] = text:sub(i, i + 999) end
    if BOT.head > 2000 then                -- compactar la cola
        local nb = {}
        for i = BOT.head, #BOT.buf do nb[#nb + 1] = BOT.buf[i] end
        BOT.buf, BOT.head = nb, 1
    end
    return #BOT.buf - BOT.head + 1, tostring(BOT.done), table.unpack(parts)
end

return "oambot cargado"

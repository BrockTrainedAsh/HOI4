-- aobgen.lua : turn a known code address into a unique, patch-tolerant AOB
-- signature ready to paste into AOBScanModule(). Wildcards the 4-byte operands
-- of relative call/jmp/jcc instructions, since those displacements shift
-- whenever surrounding code moves between patches.
--
-- How to run (Cheat Engine -> Table menu -> "Lua Engine"):
--   TOOLKIT_DIR = [[C:\Users\Brock\Documents\My Cheat Tables\HOI4-Memory-Toolkit]]
--   AOBGEN_ADDR = "hoi4.exe+1A2B3C4"   -- the injection point you found
--   AOBGEN_LEN  = 24                    -- optional, default 24 bytes
--   dofile(TOOLKIT_DIR..[[\lua\aobgen.lua]])

local DIR = TOOLKIT_DIR or [[C:\Users\Brock\Documents\My Cheat Tables\HOI4-Memory-Toolkit]]
local aob = dofile(DIR .. [[\lua\lib\aoblib.lua]])

local target = AOBGEN_ADDR
if target == nil then
  print("[aobgen] Set AOBGEN_ADDR first, e.g. AOBGEN_ADDR='hoi4.exe+1A2B3C4'")
  return
end
local addr = (type(target) == "number") and target or getAddress(target)
if addr == nil or addr == 0 then
  print("[aobgen] Could not resolve address: " .. tostring(target)); return
end

local baseLen = AOBGEN_LEN or 24

-- Mask the rel32 operand after E8 (call), E9 (jmp), and 0F 8x (jcc near).
local function buildMasked(bytes)
  local toks, i = {}, 1
  while i <= #bytes do
    local b = bytes[i]
    toks[#toks + 1] = string.format("%02X", b)
    local rel = false
    if b == 0xE8 or b == 0xE9 then
      rel = true
    elseif b == 0x0F and bytes[i + 1] ~= nil
           and bytes[i + 1] >= 0x80 and bytes[i + 1] <= 0x8F then
      toks[#toks + 1] = string.format("%02X", bytes[i + 1]) -- keep the 8x
      i = i + 1
      rel = true
    end
    if rel then
      for _ = 1, 4 do
        i = i + 1
        if bytes[i] ~= nil then toks[#toks + 1] = "??" end
      end
    end
    i = i + 1
  end
  return table.concat(toks, " ")
end

-- Grow until unique within the module (cap a bit past the requested length).
local sig, hits
for L = baseLen, baseLen + 16, 4 do
  local bytes = readBytes(addr, L, true)
  if bytes == nil then break end
  sig = buildMasked(bytes)
  hits = aob.scanInModule(sig)
  if #hits == 1 then break end
end

print(string.rep("=", 72))
print("aobgen for " .. aob.fmt(addr))
print(string.rep("=", 72))
print("raw bytes : " .. (aob.readHex(addr, baseLen) or "?"))
print("signature : " .. (sig or "?"))
if hits ~= nil then
  if #hits == 1 then
    print("status    : UNIQUE in " .. tostring(process) ..
          " -- safe to use in AOBScanModule().")
  else
    print("status    : " .. #hits .. " matches -- NOT unique yet.")
    print("            Increase AOBGEN_LEN and re-run, or pick a more")
    print("            distinctive instruction region as the anchor.")
  end
end

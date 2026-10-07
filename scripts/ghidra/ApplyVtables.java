// args: file with "vtaddr label nfuncs" -> label vtable and name its functions label_vfN (if still default-named)
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.symbol.*;
import java.nio.file.*;

public class ApplyVtables extends GhidraScript {
    public void run() throws Exception {
        int n = 0;
        for (String line : Files.readAllLines(Paths.get(getScriptArgs()[0]))) {
            String[] p = line.trim().split(" ");
            Address vt = toAddr(p[0]);
            String cls = p[1];
            int cnt = Integer.parseInt(p[2]);
            createLabel(vt, "vt_" + cls, true, SourceType.ANALYSIS);
            for (int i = 0; i < cnt; i++) {
                long fp = getInt(vt.add(i * 4)) & 0xffffffffL;
                boolean thumb = (fp & 1) != 0;
                Address fa = toAddr(fp & ~1L);
                Function f = getFunctionAt(fa);
                if (f == null && !thumb) { disassemble(fa); f = createFunction(fa, null); }
                if (f != null && f.getName().startsWith("FUN_")) {
                    f.setName(cls + "_vf" + i, SourceType.ANALYSIS); n++;
                } else if (f != null && f.getName().contains("_vf") && !f.getName().startsWith(cls)) {
                    // shared implementation; leave first name but add a label
                    createLabel(fa, cls + "_vf" + i, false, SourceType.ANALYSIS);
                }
            }
        }
        println("named " + n);
    }
}

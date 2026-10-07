// Apply "addrhex name" lines from a file as labels / function names.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.symbol.*;
import java.nio.file.*;

public class ApplySyms extends GhidraScript {
    public void run() throws Exception {
        int n = 0;
        for (String line : Files.readAllLines(Paths.get(getScriptArgs()[0]))) {
            String[] p = line.trim().split(" ", 2);
            if (p.length < 2) continue;
            Address a = toAddr(p[0]);
            Function f = getFunctionAt(a);
            if (f == null) { disassemble(a); f = createFunction(a, null); }
            if (f != null) f.setName(p[1], SourceType.IMPORTED);
            else createLabel(a, p[1], true, SourceType.IMPORTED);
            n++;
        }
        println("applied " + n);
    }
}

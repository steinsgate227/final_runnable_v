module fpDecompose_tb;
    parameter WID = 32;
    localparam EMSB = WID==32 ? 7 : 10;
    localparam FMSB = WID==32 ? 22 : 51;
    
    reg [WID-1:0] i;
    wire sgn;
    wire [EMSB:0] exp;
    wire [FMSB:0] man;
    wire [FMSB+1:0] fract;
    wire xz, mz, vz, inf, xinf, qnan, snan, nan;
    integer j;

    fpDecompose #(WID) uut (.i(i), .sgn(sgn), .exp(exp), .man(man), .fract(fract), 
        .xz(xz), .mz(mz), .vz(vz), .inf(inf), .xinf(xinf), .qnan(qnan), .snan(snan), .nan(nan));

    initial begin
        $display("Running robust simulation for fpDecompose...");
        
        // 1.0
        i = 32'h3F800000; #10;
        $display("i=%h | sgn=%b | exp=%h | vz=%b | inf=%b | nan=%b", i, sgn, exp, vz, inf, nan);

        // Infinity
        i = 32'h7F800000; #10;
        $display("i=%h | sgn=%b | exp=%h | vz=%b | inf=%b | nan=%b", i, sgn, exp, vz, inf, nan);

        for (j = 0; j < 20; j = j + 1) begin
            i = $random;
            #10;
            $display("i=%h | sgn=%b | exp=%h | vz=%b | inf=%b | nan=%b", i, sgn, exp, vz, inf, nan);
        end
        
        $display("Simulation for fpDecompose finished.");
        $finish;
    end
endmodule

module fp_cmp_unit_tb;
    parameter WID = 32;
    reg [WID-1:0] a, b;
    wire [4:0] o;
    wire nanx;
    integer j;

    fp_cmp_unit #(WID) uut (.a(a), .b(b), .o(o), .nanx(nanx));

    initial begin
        $display("Running robust simulation for fp_cmp_unit...");
        
        a = 32'h0; b = 32'h0; #10;
        $display("a=%h | b=%h | o=%b", a, b, o);

        a = 32'h40000000; b = 32'h3F800000; #10;
        $display("a=%h | b=%h | o=%b", a, b, o);

        for (j = 0; j < 20; j = j + 1) begin
            a = $random;
            b = $random;
            #10;
            $display("a=%h | b=%h | o=%b | nanx=%b", a, b, o, nanx);
        end
        
        $display("Simulation for fp_cmp_unit finished.");
        $finish;
    end
endmodule

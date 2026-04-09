module redor64_tb;
    reg [5:0] a;
    reg [63:0] b;
    wire o;
    integer j;

    redor64 uut (.a(a), .b(b), .o(o));

    initial begin
        $display("Running robust simulation for redor64...");
        
        // Fixed cases
        a = 6'd0; b = 64'h0; #10;
        $display("a=%d | b=%h | o=%b", a, b, o);
        
        a = 6'd0; b = 64'h1; #10;
        $display("a=%d | b=%h | o=%b", a, b, o);

        a = 6'd10; b = 64'h0; #10;
        $display("a=%d | b=%h | o=%b (should be 0)", a, b, o);

        a = 6'd10; b = 64'h400; #10;
        $display("a=%d | b=%h | o=%b (should be 1)", a, b, o);

        for (j = 0; j < 20; j = j + 1) begin
            a = $random % 64;
            b = {$random, $random};
            #10;
            $display("a=%d | b=%h | o=%b", a, b, o);
        end
        
        $display("Simulation for redor64 finished.");
        $finish;
    end
endmodule

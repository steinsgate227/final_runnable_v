module F80ToF32_tb;
    reg [79:0] a;
    wire [31:0] o;
    integer j;

    F80ToF32 uut (.a(a), .o(o));

    initial begin
        $display("Running robust simulation for F80ToF32...");
        
        // Test cases
        a = {1'b0, 15'h3FFF, 64'h8000000000000000}; // 1.0 in extended precision
        #10;
        $display("a=%h (1.0) | o=%h", a, o);

        a = {1'b0, 15'h4000, 64'h8000000000000000}; // 2.0
        #10;
        $display("a=%h (2.0) | o=%h", a, o);

        a = 80'h0; // 0.0
        #10;
        $display("a=%h (0.0) | o=%h", a, o);

        for (j = 0; j < 20; j = j + 1) begin
            a[79:64] = $random;
            a[63:32] = $random;
            a[31:0] = $random;
            #10;
            $display("a=%h | o=%h", a, o);
        end
        
        $display("Simulation for F80ToF32 finished.");
        $finish;
    end
endmodule

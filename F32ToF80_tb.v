module F32ToF80_tb;
    reg [31:0] a;
    wire [79:0] o;
    integer j;

    F32ToF80 uut (.a(a), .o(o));

    initial begin
        $display("Running robust simulation for F32ToF80...");
        
        // Test cases
        a = 32'h3F800000; // 1.0
        #10;
        $display("a=%h (1.0) | o=%h", a, o);

        a = 32'h40000000; // 2.0
        #10;
        $display("a=%h (2.0) | o=%h", a, o);

        a = 32'h00000000; // 0.0
        #10;
        $display("a=%h (0.0) | o=%h", a, o);

        for (j = 0; j < 20; j = j + 1) begin
            a = $random;
            #10;
            $display("a=%h | o=%h", a, o);
        end
        
        $display("Simulation for F32ToF80 finished.");
        $finish;
    end
endmodule

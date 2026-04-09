module fd2s_tb;
    reg [63:0] a;
    wire [31:0] o;
    integer j;

    fd2s uut (.a(a), .o(o));

    initial begin
        $display("Running robust simulation for fd2s...");
        
        a = 64'h3FF0000000000000; // 1.0
        #10;
        $display("a=%h (1.0) | o=%h", a, o);

        a = 64'h4000000000000000; // 2.0
        #10;
        $display("a=%h (2.0) | o=%h", a, o);

        for (j = 0; j < 20; j = j + 1) begin
            a[63:32] = $random;
            a[31:0] = $random;
            #10;
            $display("a=%h | o=%h", a, o);
        end
        
        $display("Simulation for fd2s finished.");
        $finish;
    end
endmodule

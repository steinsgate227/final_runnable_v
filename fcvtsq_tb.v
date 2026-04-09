module fcvtsq_tb;
    reg [31:0] a;
    wire [127:0] o;
    integer j;

    fcvtsq #(128) uut (.a(a), .o(o));

    initial begin
        $display("Running robust simulation for fcvtsq...");
        
        a = 32'h3F800000; // 1.0
        #10;
        $display("a=%h (1.0) | o=%h", a, o);

        a = 32'h40000000; // 2.0
        #10;
        $display("a=%h (2.0) | o=%h", a, o);

        for (j = 0; j < 20; j = j + 1) begin
            a = $random;
            #10;
            $display("a=%h | o=%h", a, o);
        end
        
        $display("Simulation for fcvtsq finished.");
        $finish;
    end
endmodule

module fs2d_tb;
    reg [39:0] a;
    wire [79:0] o;
    integer j;

    fs2d uut (.a(a), .o(o));

    initial begin
        $display("Running robust simulation for fs2d...");
        
        a = 40'h3F80000000; // Simplified 1.0 (assuming 40-bit layout similar to 32-bit but wider mantissa)
        #10;
        $display("a=%h | o=%h", a, o);

        for (j = 0; j < 20; j = j + 1) begin
            a = {$random, $random[7:0]};
            #10;
            $display("a=%h | o=%h", a, o);
        end
        
        $display("Simulation for fs2d finished.");
        $finish;
    end
endmodule

module delay_tb;
    reg clk;
    reg ce;
    reg [3:0] i;
    wire [3:0] o1, o2, o3;
    integer j;

    delay1 #(4) u1 (.clk(clk), .ce(ce), .i(i), .o(o1));
    delay2 #(4) u2 (.clk(clk), .ce(ce), .i(i), .o(o2));
    delay3 #(4) u3 (.clk(clk), .ce(ce), .i(i), .o(o3));

    initial begin
        clk = 0;
        ce = 1;
        i = 0;
        $display("Running robust simulation for delay...");
        
        for (j = 0; j < 20; j = j + 1) begin
            @(posedge clk);
            i <= $random;
            #1;
            $display("Time=%t | i=%h | o1=%h | o2=%h | o3=%h", $time, i, o1, o2, o3);
        end
        
        $display("Simulation for delay finished.");
        $finish;
    end

    always #5 clk = ~clk;
endmodule

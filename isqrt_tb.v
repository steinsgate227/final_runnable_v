module isqrt_tb;
    parameter WID = 16;
    reg rst, clk, ce, ld;
    reg [WID-1:0] a;
    wire [WID*2-1:0] o;
    wire done;
    integer j;

    isqrt #(WID) uut (.rst(rst), .clk(clk), .ce(ce), .ld(ld), .a(a), .o(o), .done(done));

    initial begin
        clk = 0;
        rst = 1;
        ce = 1;
        ld = 0;
        a = 0;
        $display("Running robust simulation for isqrt...");
        
        #100 rst = 0;
        #100;
        
        // Fixed case: sqrt(256) = 16
        wait(done == 1);
        @(posedge clk);
        a = 16'd256;
        ld = 1;
        @(posedge clk);
        ld = 0;
        
        #100;
        wait(done == 1);
        $display("a=%d | o=%h (should be 16 in integer part)", a, o);

        for (j = 0; j < 15; j = j + 1) begin
            wait(done == 1);
            @(posedge clk);
            a = $random % 1000 + 1;
            ld = 1;
            @(posedge clk);
            ld = 0;
            $display("Test Case %0d: a=%d", j, a);
            #100;
            wait(done == 1);
            $display("Result: o=%h", o);
            #100;
        end
        
        $display("Simulation for isqrt finished.");
        $finish;
    end

    always #5 clk = ~clk;
endmodule

module fpdivr8_tb();
    parameter WID = 16;
    reg rst;
    reg clk;
    reg ld;
    reg [WID-1:0] a, b;
    wire [WID-1:0] q;
    wire [WID-1:0] r;
    wire done;
    wire [7:0] lzcnt;
    integer j;

    fpdivr8 #(WID) uut (.clk(clk), .ld(ld), .a(a), .b(b), .q(q), .r(r), .done(done), .lzcnt(lzcnt));

    initial begin
        clk = 0;
        rst = 1;
        ld = 0;
        a = 0;
        b = 0;
        $display("Running robust simulation for fpdivr8...");
        
        #100 rst = 0;
        #100;
        
        for (j = 0; j < 15; j = j + 1) begin
            wait(done == 1);
            @(posedge clk);
            a = $random % 1000 + 1;
            b = $random % 10 + 1;
            ld = 1;
            @(posedge clk);
            ld = 0;
            $display("Test Case %0d: a=%d | b=%d", j, a, b);
            
            // Wait for it to finish
            #100;
            wait(done == 1);
            $display("Result: q=%d (hex:%h) | r=%d | done=%b", q, q, r, done);
            #100;
        end
        
        $display("Simulation for fpdivr8 finished.");
        $finish;
    end

    always #5 clk = ~clk;
endmodule



